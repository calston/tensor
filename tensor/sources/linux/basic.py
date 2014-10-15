from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Event, Source

class LoadAverage(Source):
    implements(ITensorSource)

    def get(self):
        la1 = open('/proc/loadavg', 'rt').read().split()[0]

        return Event('ok', self.config['service'], 'Load average', float(la1))


class DiskIO(Source):
    implements(ITensorSource)

    def get(self):
        # I can't think of a useful way to filter /proc/diskstats right now
        return None
