#!/usr/bin/env python

import os
import irclib
import yaml

import standup


def load_config():
    """ Load the configuration file """
    rootdir = os.path.dirname(__file__)
    with file(os.path.join(rootdir, 'config.yml')) as f:
        return yaml.load(f)

def print_event(event):
    """ Print an event on stdout """
    def print_callback(connection, ev):
        print '{0}, {1}, {2}: {3}'.format(
                event,
                ev.source(),
                ev.target(),
                ' '.join(ev.arguments()),
                )
    irc.add_global_handler(event, print_callback)


if __name__ == '__main__':
    irc = irclib.IRC()
    # Will log all events to stdout
    for event in irclib.all_events:
        print_event(event)
    server = irc.server()
    cfg = load_config()
    server.connect(
            cfg['network'],
            cfg['port'],
            cfg['nick'],
            ircname=cfg['name'])
    server.join(cfg['channel'])
    # Launch all configured Standups
    for name in cfg['standups']:
        standup.Standup(name, irc, server, cfg, cfg['standups'][name]).run()
    irc.process_forever()
