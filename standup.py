
import time
import shlex


class Standup(object):

    def __init__(self, name, irc, server, global_config, config):
        self._name = name
        self._irc = irc
        self._server = server
        self._global_config = global_config
        self._config = config
        self._in_progress = False
        self._starting = False
        self._owner = None
        self._started = None
        self._parking = None
        self._user_list = None
        self._current_user = None

    def _register_handlers(self):
        self._irc.add_global_handler('pubmsg', self._event_pubmsg)

    def _event_pubmsg(self, conn, event):
        args = event.arguments()
        if not args:
            return
        if args[0].startswith(self._global_config['nick']):
            self._direct_message(event)

    def _direct_message(self, event):
        target = event.target()
        if target != self._config['standup_channel']:
            # Ignoring command outside the standup channel
            # So we can spawn several standup easily
            return
        args = shlex.split(event.arguments()[0])
        nick = event.source().split('!')[0]
        args.pop(0)
        f_cmd = '_cmd_' + args[0]
        if hasattr(self, f_cmd):
            args.pop(0)
            getattr(self, f_cmd)(target, nick, args)

    def _cmd_help(self, target, nick, args):
        if not args:
            self._send_msg(target, nick, ('My commands are: start, stop, next, skip, park.'
                ' Ask me "help <command>" for what they do.'))
            return
        cmd = args[0]
        if cmd == 'start':
            self._send_msg(target, nick, 'start: start a standup')
        elif cmd == 'stop':
            self._send_msg(target, nick, 'stop: stop a standup')
        elif cmd == 'next':
            self._send_msg(target, nick, 'next: when you are done talking')
        elif cmd == 'skip':
            self._send_msg(target, nick, 'skip <nick>: skip a person')
        elif cmd == 'park':
            self._send_msg(target, nick, 'park <topic>: park a topic for later')
        else:
            self._send_msg(target, nick, 'WTF?! Try "help"')

    def _cmd_start(self, target, nick, args):
        """ This function starts a standup

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
            nick = event.source().split('!')[0]
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
            self._parking = []
            self._server.privmsg(self._config['standup_channel'],
                    'Let\'s start the standup with {0}'.format(', '.join(nick_list)))
            self._user_list = nick_list
            self._current_user = nick_list[0]
            self._send_msg(self._config['standup_channel'], self._current_user,
                    'You start.')
        self._irc.execute_at(time.time() + self._config['warmup_duration'], start)

    def _cmd_next(self, target=None, nick=None, args=None):
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        if nick and nick != self._current_user:
            self._send_msg(target, nick, 'Only {0} can say "next".'.format(self._current_user))
            return
        self._user_list.pop()
        if not self._user_list:
            self._cmd_stop()
            return
        self._current_user = self._user_list[0]
        self._send_msg(self._config['standup_channel'], self._current_user,
                'You\'re next.')

    def _cmd_skip(self, target, nick, args):
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        if target != self._config['standup_channel']:
            # Wrong channel, ignoring
            return
        if self._owner and nick and self._owner != nick:
            self._send_msg(target, nick, 'Only {0} can skip someone (he started the standup).'.format(nick))
            return
        to_skip = args[0]
        if to_skip == self._current_user:
            self._cmd_next()
            return
        self._user_list.remove(to_skip)
        self._send_msg(target, nick, '{0} has been removed from the standup.'.format(to_skip))

    def _cmd_park(self, target, nick, args):
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        self._parking.append(' '.join(args))
        self._send_msg(target, nick, 'Parked.')

    def _cmd_stop(self, target=None, nick=None, args=None):
        if self._in_progress is False:
            self._send_msg(target, nick, 'No standup in progress.')
            return
        if self._owner and nick and self._owner != nick:
            self._send_msg(target, nick, 'Only {0} can stop the standup (he started it).'.format(nick))
            return
        self._in_progress = False
        self._user_list = None
        self._current_user = None
        if self._started is None:
            self._server.privmsg(self._config['standup_channel'],
                    'Standup stopped.')
            return
        elapsed = int((time.time() - self._started) / 60)
        self._server.privmsg(self._config['standup_channel'],
                'All done! Standup was {0} minutes.'.format(elapsed))
        if self._parking:
            self._server.privmsg(self._config['primary_channel'], 'Parked topics from "{0}" standup:'.format(self._name))
            send = lambda m: self._server.privmsg(self._config['primary_channel'], '* ' + m)
            for park in self._parking:
                send(park)
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
