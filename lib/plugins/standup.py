
import os
import time
import archives


class Standup(object):

    def __init__(self, name, irc, server, global_config, config):
        self._name = name
        archives_path = os.path.join(os.path.expanduser(global_config['logs']),
                'standup_archives')
        self._archives = archives.DiskArchives(archives_path, global_config, config)
        self._irc = irc
        self._server = server
        self._global_config = global_config
        self._config = config
        self._in_progress = False
        self._starting = False
        self._owner = None
        self._started = None
        self._parking = None
        self._user_late_list = None
        self._user_list = None
        self._current_user = None

    def _register_handlers(self):
        self._irc.add_global_handler('pubmsg', self._event_pubmsg)

    def _event_pubmsg(self, conn, event):
        args = event.arguments()
        if not args:
            return
        if self._in_progress is True and event.target() == self._config['standup_channel']:
            # Archiving
            nick = event.source().split('!')[0].lower()
            self._archives.write('{0}: {1}'.format(nick, args[0]))
        if args[0].startswith(self._global_config['nick']):
            self._direct_message(event)

    def _direct_message(self, event):
        target = event.target()
        if target != self._config['standup_channel']:
            # Ignoring command outside the standup channel
            # So we can spawn several standup easily
            return
        args = [arg for arg in event.arguments()[0].split(' ') if arg]
        nick = event.source().split('!')[0].lower()
        args.pop(0)
        if not args:
            return
        f_cmd = '_cmd_' + args[0].lower()
        if hasattr(self, f_cmd):
            args.pop(0)
            getattr(self, f_cmd)(target, nick, args)

    def _cmd_help(self, target, nick, args):
        """ Display the help menu """
        options = {}
        for meth in dir(self):
            if not meth.startswith('_cmd_'):
                continue
            cmeth = getattr(self, meth)
            doc = cmeth.__doc__.split('\n')[0].strip() if cmeth.__doc__ else '<undocumented>'
            options[meth[5:]] = doc
        if not args:
            self._send_msg(target, nick, ('My commands are: {0}. Ask me '
                '"help <command>" for what they do.').format(', '.join(options.keys())))
            return
        cmd = args[0].lower()
        if cmd in options:
            self._send_msg(target, nick, options[cmd])
            return
        self._send_msg(target, nick, 'WTF?! Try "help"')

    def _cmd_start(self, target, nick, args):
        """ start: start a standup

        1/ all users on the standup channel are asked to say something
        2/ all replies are gathered for 1 min
        3/ starts the standup with the users who replied
        """
        if self._starting is True or self._in_progress is True:
            self._send_msg(target, nick, 'Cannot start a standup twice.')
            return
        self._owner = nick
        self._server.privmsg(self._config['primary_channel'],
                'Starting a daily standup "{0}" on {1}'.format(self._name, self._config['standup_channel']))
        self._starting = True
        def list_users(conn, event):
            self._irc.remove_global_handler('namreply', list_users)
            users = event.arguments().pop().split(' ')
            users.pop(0)
            if self._global_config['nick'] in users:
                users.remove(self._global_config['nick'])
            users = map(lambda c: c.lstrip('@+'), users)
            self._server.privmsg(self._config['standup_channel'],
                    '{0}: Please say something to be part of the standup (starting in {1} seconds)'.format(
                        ', '.join(users), self._config['warmup_duration']))
        self._irc.add_global_handler('namreply', list_users)
        self._server.names([self._config['standup_channel']])
        nick_list = []
        def gather_reply(conn, event):
            if self._starting is False:
                return
            if event.target() != self._config['standup_channel']:
                return
            nick = event.source().split('!')[0].lower()
            if nick not in nick_list:
                nick_list.append(nick)
        self._irc.add_global_handler('pubmsg', gather_reply)
        def start():
            self._starting = False
            self._in_progress = True
            self._started = time.time()
            # Stop gathering
            self._irc.remove_global_handler('pubmsg', gather_reply)
            if not nick_list:
                self._server.privmsg(self._config['standup_channel'],
                        'Nobody replied, aborting the standup.')
                return
            self._archives.new(self._name)
            self._user_late_list = []
            self._parking = []
            self._server.privmsg(self._config['standup_channel'],
                    'Let\'s start the standup with {0}'.format(', '.join(nick_list)))
            self._archives.write('*** Starting with: {0}'.format(', '.join(nick_list)))
            self._user_list = nick_list
            self._current_user = nick_list[0]
            self._send_msg(self._config['standup_channel'], self._current_user,
                    'You start.')
            self._set_speak_timer()
            self._archives.write('*** Current: {0}'.format(self._current_user))
        self._irc.execute_at(int(time.time() + self._config['warmup_duration']), start)

    def _set_speak_timer(self):
        nick = self._current_user
        def warn_user():
            if self._in_progress is False or self._current_user != nick:
                return
            self._send_msg(self._config['standup_channel'], self._current_user,
                    'Hurry up! You reached {0} minutes!'.format(self._config['speak_limit']))
        self._irc.execute_at(int(time.time() + self._config['speak_limit'] * 60), warn_user)

    def _cmd_add(self, target, nick, args):
        """ Add a person to the standup (I won't check if the nick exists on the server) """
        if not args:
            return
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        to_add = args[0].lower()
        if to_add == 'me':
            to_add = nick
        if nick and self._owner != nick and to_add != nick:
            self._send_msg(target, nick, 'Only {0} can add someone (he started the standup).'.format(self._owner))
            return
        if to_add in self._user_list:
            self._send_msg(target, nick, '{0} is already part of the Standup.'.format(to_add))
            return
        # FIXME: Check if to_add exists for real
        self._user_list.append(to_add)
        self._user_late_list.append(to_add)
        if to_add == nick:
            self._send_msg(target, nick, 'You\'re in.')
            return
        self._send_msg(target, nick, 'Added {0}.'.format(to_add))

    def _cmd_next(self, target=None, nick=None, args=None):
        """ next: when you are done talking """
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        if nick and nick != self._current_user:
            self._send_msg(target, nick, 'Only {0} can say "next".'.format(self._current_user))
            return
        self._user_list.pop(0)
        if not self._user_list:
            self._cmd_stop()
            return
        self._current_user = self._user_list[0]
        self._send_msg(self._config['standup_channel'], self._current_user,
                'You\'re next.')
        self._set_speak_timer()
        self._archives.write('*** Current: {0}'.format(self._current_user))

    def _cmd_skip(self, target, nick, args):
        """ skip <nick>: skip a person """
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        if target != self._config['standup_channel']:
            # Wrong channel, ignoring
            return
        if self._owner and nick and self._owner != nick:
            self._send_msg(target, nick, 'Only {0} can skip someone (he started the standup).'.format(self._owner))
            return
        if not args:
            return
        to_skip = args[0].lower()
        if to_skip == self._current_user:
            self._cmd_next()
            return
        if to_skip not in self._user_list:
            return
        self._user_list.remove(to_skip)
        self._send_msg(target, nick, '{0} has been removed from the standup.'.format(to_skip))

    def _cmd_park(self, target, nick, args):
        """ park <topic>: park a topic for later """
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        self._parking.append('({0}) {1}'.format(nick, ' '.join(args)))
        self._send_msg(target, nick, 'Parked.')

    def _cmd_stop(self, target=None, nick=None, args=None):
        """ stop: stop a standup """
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        if self._owner and nick and self._owner != nick:
            self._send_msg(target, nick, 'Only {0} can stop the standup (he started it).'.format(self._owner))
            return
        self._user_list = None
        self._current_user = None
        self._in_progress = False
        elapsed = int((time.time() - self._started) / 60)
        self._started = None
        self._server.privmsg(self._config['standup_channel'],
                'All done! Standup was {0} minutes.'.format(elapsed))
        user_late_list = ', '.join(self._user_late_list)
        self._archives.write('*** Standup was {0} minutes'.format(elapsed))
        if user_late_list:
            self._server.privmsg(self._config['primary_channel'], 'Late people on "{0}" standup: {1}'.format(
                self._name, user_late_list))
            self._archives.write('*** Late people: {0}'.format(user_late_list))
        if self._parking:
            self._archives.write('Parked topics: ')
            self._server.privmsg(self._config['primary_channel'], 'Parked topics from "{0}" standup:'.format(self._name))
            send = lambda m: self._server.privmsg(self._config['primary_channel'], m)
            for park in self._parking:
                send('* ' + park)
                self._archives.write('* ' + park)
        self._archives.close()
        self._parking = False

    def _send_msg(self, target, nick, msg):
        """ Send a message to a nick and target
        Each message sent is prefixed by the nick name (use to talk to someone)
        """
        if hasattr(msg, '__iter__'):
            for m in msg:
                self._server.privmsg(target, '{0}: {1}'.format(nick, m))
            return
        self._server.privmsg(target, '{0}: {1}'.format(nick, msg))

    def run(self):
        self._register_handlers()
        self._server.join(self._config['primary_channel'])
        self._server.join(self._config['standup_channel'])
