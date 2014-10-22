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

    def __init__(self, config, qb):
        Source.__init__(self, config, qb)

        self.cpu = None

    def get(self):
        stat = open('/proc/stat', 'rt').readline().strip('\n')

        cpu = [int(i) for i in stat.split()[1:]]

        user, nice, system, idle, iowait, irq, \
            softirq, steal, guest, guest_nice = cpu
 
        # I got this off the internet, it's probably wrong
        idle = idle + iowait
        total = user + nice + system + irq + softirq + steal + idle

        if not self.cpu:
            # No initial values so just return zero on the first get
            self.cpu = (idle, total)
            return self.createEvent('ok', 'CPU %', 0.0)
        
        prev_idle, prev_total = self.cpu
        
        total_diff = total - prev_total

        if total_diff != 0:
            cpu_util = (total_diff - (idle - prev_idle))/float(total_diff)
        else:
            cpu_util = 0.0

        self.cpu = (idle, total)

        return self.createEvent('ok', 'CPU %s%%' % int(cpu_util*100), cpu_util)

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
        out, err, code = yield fork('/bin/df', args=('-lPx','tmpfs',))

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

