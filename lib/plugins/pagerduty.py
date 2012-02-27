
import time
import datetime
import signal

import pytz
import requests
import simplejson as json


PAGER_DUTY_URL=('https://{organization}.pagerduty.com/api/v1/schedules/'
        '{schedule}/entries?since={date}T12:00:00-07&until={date}T12:00:00-07')


class PagerDuty(object):

    def __init__(self, irc, server, config):
        self._irc = irc
        self._server = server
        self._global_config = config
        self._config = config['pagerduty']

    def _get_rotation(self):
        ret = {}
        dt = datetime.datetime.now()
        date = '{0}-{1:02}-{2:02}'.format(dt.year, dt.month, dt.day)
        for label, schedule in self._config['schedules'].iteritems():
            url = PAGER_DUTY_URL.format(organization=self._config['organization'],
                    schedule=schedule,
                    date=date)
            r = requests.get(url, auth=tuple(self._config['auth'].split(':')))
            data = json.loads(r.text)
            if data['total'] < 1:
                continue
            data = data['entries'][0]['user']
            if data['email'] not in self._config['users']:
                continue
            data['nick'] = self._config['users'][data['email']]
            ret[label] = data
        return ret

    def _announce_rotation(self, *args):
        rotation = self._get_rotation()
        topic = []
        for label, user in rotation.iteritems():
            topic.append('{0} ({1}) is assigned to "{2}"'.format(user['nick'],
                user['name'].encode('utf8'), label))
            self._server.privmsg(user['nick'], 'You are on rotation "{0}"'.format(label))
            self._server.privmsg(self._global_config['channel'],
                    '* {0} ({1}) is on rotation "{2}"'.format(user['nick'],
                        user['name'].encode('utf8'), label))
        # Set topic
        topic = 'Today\'s rotation: {0}'.format(' // '.join(topic))
        self._server.topic(self._global_config['channel'], topic)
        # Check if we are called by a signal handler
        if args:
            return
        # No, so let's reschedule the announcement
        self._schedule_announcement()

    def _schedule_announcement(self):
        tz = pytz.timezone(self._global_config['timezone'])
        dt = datetime.datetime.now(tz)
        schedule = self._config['announce_hour']
        if dt.hour < schedule:
            td = datetime.timedelta(hours=(schedule - dt.hour),
                    minutes=(-dt.minute), seconds=(-dt.second),
                    microseconds=(-dt.microsecond))
        else:
            td = datetime.timedelta(hours=(24 - (dt.hour - schedule)),
                    minutes=(-dt.minute), seconds=(-dt.second),
                    microseconds=(-dt.microsecond))
        total_seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
        self._irc.execute_at(time.time() + total_seconds, self._announce_rotation)

    def run(self):
        # Register the rotation announcement on SIGUSR1
        signal.signal(signal.SIGUSR1, self._announce_rotation)
        self._schedule_announcement()
