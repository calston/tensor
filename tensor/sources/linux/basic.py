from zope.interface import implements

from twisted.internet import defer

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork


class LoadAverage(Source):
    """Reports system load average for the current host

    **Metrics:**

    :(service name): Load average
    """
    implements(ITensorSource)

    def get(self):
        la1 = open('/proc/loadavg', 'rt').read().split()[0]

        return self.createEvent('ok', 'Load average', float(la1))


class DiskIO(Source):
    implements(ITensorSource)

    def get(self):
        # I can't think of a useful way to filter /proc/diskstats right now
        return None


class CPU(Source):
    """Reports system CPU utilisation as a percentage/100

    **Metrics:**

    :(service name): Percentage CPU utilisation
    """
    implements(ITensorSource)

    def __init__(self, *a):
        Source.__init__(self, *a)

        self.cpu = None

    def _read_proc_stat(self):
        with open('/proc/stat', 'rt') as procstat:
            return procstat.readline().strip('\n')

    def _calculate_metrics(self, stat):
        cpu = [int(i) for i in stat.split()[1:]]
        # We might not have all the virt-related numbers, so zero-pad.
        cpu = (cpu + [0, 0, 0])[:10]

        (user, nice, system, idle, iowait, irq,
         softirq, steal, guest, guest_nice) = cpu
        usage = user + nice + system + irq + softirq + steal
        total = usage + iowait + idle

        return (usage, iowait, total)

    def get(self):
        stat = self._read_proc_stat()
        usage, iowait, total = self._calculate_metrics(stat)

        if not self.cpu:
            # No initial values, so set to the current values to return zeros.
            self.cpu = (usage, iowait, total)

        prev_usage, prev_iowait, prev_total = self.cpu
        self.cpu = (usage, iowait, total)
        total_diff = total - prev_total

        if total_diff != 0:
            cpu_usage = (usage - prev_usage) / float(total_diff)
            cpu_iowait = (iowait - prev_iowait) / float(total_diff)
        else:
            cpu_usage = 0.0
            cpu_iowait = 0.0

        return [
            self.createEvent(
                'ok', 'CPU %s%%' % int(cpu_usage * 100), cpu_usage),
            self.createEvent(
                'ok', 'CPU iowait %s%%' % (cpu_iowait * 100), cpu_iowait,
                prefix='iowait'),
        ]


class Memory(Source):
    """Reports system memory utilisation as a percentage/100

    **Metrics:**

    :(service name): Percentage memory utilisation
    """
    implements(ITensorSource)

    def get(self):
        mem = open('/proc/meminfo')
        dat = {}
        for l in mem:
            k, v = l.replace(':', '').split()[:2]
            dat[k] = int(v)

        free = dat['MemFree'] + dat['Buffers'] + dat['Cached']
        total = dat['MemTotal']
        used = total - free

        return self.createEvent('ok', 'Memory %s/%s' % (used, total),
                                used/float(total))


class DiskFree(Source):
    """Returns the free space for all mounted filesystems

    **Metrics:**

    :(service name).(device): Used space (%)
    """
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        out, err, code = yield fork('/bin/df', args=('-lPx', 'tmpfs',))

        out = [i.split() for i in out.strip('\n').split('\n')[1:]]

        events = []

        for disk, size, used, free, util, mount in out:
            if disk != "udev":
                util = int(util.strip('%'))
                events.append(
                    self.createEvent('ok', 'Disk usage %s' % (util),
                                     util, prefix=disk)
                )

        defer.returnValue(events)
