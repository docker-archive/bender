
import select
from irc.client import IRC
from irc.events import all as all_events
import yaml


class Bender(object):

    def __init__(self, config_path):
        with file(config_path) as f:
            self._config = yaml.load(f)

    def _set_print_handler(self, irc, event):
        """ Print an event on stdout """
        def print_callback(connection, ev):
            args = [arg.encode('ascii', 'replace') for arg in ev.arguments]
            print '{0}, {1}, {2}: {3}'.format(
                    event,
                    ev.source,
                    ev.target,
                    ' '.join(args),
                    )
        irc.add_global_handler(event, print_callback)

    def _load_plugins(self, irc, server):
        from plugins import standup, pagerduty
        # Launch all configured Standups
        for name in self._config['standups']:
            standup.Standup(name, irc, server, self._config, self._config['standups'][name]).run()
        # PagerDuty notifications
        if 'pagerduty' in self._config:
            pagerduty.PagerDuty(irc, server, self._config).run()

    def run(self):
        irc = IRC()
        # Will log all events to stdout
        for event in all_events:
            self._set_print_handler(irc, event)
        server = irc.server()
        server.connect(
                self._config['network'],
                self._config['port'],
                self._config['nick'],
                ircname=self._config['name'])
        server.join(self._config['channel'], key=self._config.get('channel_password', ''))
        self._load_plugins(irc, server)
        while True:
            try:
                # Signals makes the select to exit
                irc.process_forever()
            except select.error:
                pass

        # handle private messages, to see if there's a need for
        # authentification requests 
        irc.add_global_handler('privnotice', self._event_notice)

    def _event_notice(self, conn, event):
        args = event.arguments
        if not args:
            return
        nick = event.source.split('!')[0].lower()
        if nick == "nickserv":
            if 'registered' in ''.join(args):
                self._server.privmsg(nick, 'identify {0}'.format(self._global_config.get('password')))
