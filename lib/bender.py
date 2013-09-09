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
            print '{0}, {1}, {2}: {3}'.format(
                    event,
                    ev.source,
                    ev.target,
                    ' '.join(ev.arguments),
                    )
        irc.add_global_handler(event, print_callback)

    def _load_plugins(self, irc, server):
        from plugins import standup, pagerduty
        # Launch all configured Standups
        for name in self._config['standups']:
            standup.Standup(name, irc, server, self._config, self._config['standups'][name]).run()
        # PagerDuty notifications
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
        server.join(self._config['channel'])
        self._load_plugins(irc, server)
        while True:
            try:
                # Signals makes the select to exit
                irc.process_forever()
            except select.error:
                pass
