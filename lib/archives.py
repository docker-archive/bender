
import os
import datetime
import pytz


class Archives(object):

    def __init__(self, path, global_config, config):
        self._basepath = path
        self._timezone = None
        self._file = None

        timezone = global_config.get('timezone')
        if timezone:
            self._timezone = pytz.timezone(timezone)

    def new(self, name):
        d = datetime.datetime.now(self._timezone)
        path = os.path.join(self._basepath, '{0:02}'.format(d.year),
                '{0:02}'.format(d.month))
        if not os.path.exists(path):
            os.makedirs(path)
        filename = '{0:02}-{1:02}-{2:02}_{3:02}:{4:02}_{5}.log'.format(
                d.year, d.month, d.day, d.hour, d.minute, name)
        self._file = file(os.path.join(path, filename), 'w')

    def close(self):
        if self._file:
            self._file.close()

    def write(self, string):
        d = datetime.datetime.now(self._timezone)
        print >>self._file, '{0:02}:{1:02}:{2:02} {3}'.format(d.hour,
                d.minute, d.second, string)
        self._file.flush()
