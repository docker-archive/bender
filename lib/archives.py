
import os
import datetime
import pytz
import socket
import smtplib
from email.mime.text import MIMEText


class DiskArchives(object):
    """Archive standup logs to disk"""

    def __init__(self, global_config, config):
        self._basepath = os.path.join(os.path.expanduser(global_config['logs']),
                config.get('logfile_name', 'standup_archives'))

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
        # Mode 'wr+' required for EmailDiskArchives
        self._file = file(os.path.join(path, filename), 'wr+')

    def close(self):
        if self._file:
            self._file.close()

    def write(self, string):
        d = datetime.datetime.now(self._timezone)
        print >>self._file, '{0:02}:{1:02}:{2:02} {3}'.format(d.hour,
                d.minute, d.second, string)
        if self._file:
            self._file.flush()


class EmailDiskArchives(DiskArchives):
    """Send standup logs to configurable email address"""

    def __init__(self, global_config, config):
        self._global_config = global_config
        self._config = config
        self._to = config.get('send_logs_to')
        self._from = config.get('send_logs_from')
        self._email_active = (self._to and self._from)    # Disable if not configured
        DiskArchives.__init__(self, global_config, config)

    def close(self):
        if self._file and self._email_active:
            self._file.seek(0)
            log = self._file.read()
            msg = MIMEText(log)
            msg['Subject'] = 'Standup logs from {standup_channel}' \
                .format(**self._config)
            msg['From'] = self._from
            msg['To'] = ",".join(self._to)
            smtp_server = self._global_config.get('smtp_server', '127.0.0.1')
            try:
                s = smtplib.SMTP(smtp_server)
                s.sendmail(msg['From'], self._to, msg.as_string())
                s.quit()
            except socket.error as e:
                print 'Warning: cannot send email report {0}'.format(e)
        DiskArchives.close(self)

