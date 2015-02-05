from zope.interface import implements

from twisted.internet import defer

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork
from tensor.aggregators import Counter64


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
    :(service name).(type): Percentage CPU utilisation by type
    """
    implements(ITensorSource)

    cols = ['user', 'nice', 'system', 'idle', 'iowait', 'irq',
        'softirq', 'steal', 'guest', 'guest_nice']

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

        if not self.cpu:
            # No initial values, so set them and return no events.
            self.cpu = cpu
            self.prev_total = total
            self.prev_usage = usage
            return None

        total_diff = total - self.prev_total

        if total_diff != 0:
            metrics = [(None, (usage - self.prev_usage) / float(total_diff))]

            for i, name in enumerate(self.cols):
                prev = self.cpu[i]
                cpu_m = (cpu[i] - prev) / float(total_diff)

                metrics.append((name, cpu_m))

            self.cpu = cpu
            self.prev_total = total
            self.prev_usage = usage

            return metrics

        return None

    def get(self):
        stat = self._read_proc_stat()
        stats = self._calculate_metrics(stat)
        
        if stats:
            events = [
                self.createEvent('ok', 'CPU %s %s%%' % (name, int(cpu_m * 100)), cpu_m, prefix=name)
                for name, cpu_m in stats[1:]
            ]

            events.append(self.createEvent(
                'ok', 'CPU %s%%' % int(stats[0][1] * 100), stats[0][1]))

            return events


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
    :(service name).(device).bytes: Used space (kbytes)
    :(service name).(device).free: Free space (kbytes)
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
                used = int(used)
                free = int(free)
                events.extend([
                    self.createEvent('ok', 'Disk usage %s%%' % (util),
                                     util, prefix=disk),
                    self.createEvent('ok', 'Disk usage %s kB' % (used),
                                     used, prefix="%s.bytes" % disk),
                    self.createEvent('ok', 'Disk free %s kB' % (free),
                                     free, prefix="%s.free" % disk)
                ])

        defer.returnValue(events)

class Network(Source):
    """Returns all network interface statistics

    **Metrics:**

    :(service name).(device).tx_bytes: Bytes transmitted
    :(service name).(device).tx_packets: Packets transmitted
    :(service name).(device).tx_errors: Errors
    :(service name).(device).rx_bytes: Bytes received
    :(service name).(device).rx_packets: Packets received
    :(service name).(device).rx_errors: Errors
    """
    implements(ITensorSource)

    def _readStats(self):
        proc_dev = open('/proc/net/dev', 'rt').read()

        return proc_dev.strip('\n').split('\n')[2:]

    def get(self):
        ev = []

        for stat in self._readStats():
            items = stat.split()
            iface = items[0].strip(':')
            tx_bytes = int(items[1])
            tx_packets = int(items[2])
            tx_err = int(items[3])
            rx_bytes = int(items[9])
            rx_packets = int(items[10])
            rx_err = int(items[11])
            
            ev.extend([
                self.createEvent('ok',
                    'Network %s TX bytes/sec' % (iface),
                    tx_bytes, prefix='%s.tx_bytes' % iface,
                    aggregation=Counter64),
                self.createEvent('ok',
                    'Network %s TX packets/sec' % (iface),
                    tx_packets, prefix='%s.tx_packets' % iface,
                    aggregation=Counter64),
                self.createEvent('ok',
                    'Network %s TX errors/sec' % (iface),
                    tx_err, prefix='%s.tx_errors' % iface,
                    aggregation=Counter64),
                self.createEvent('ok',
                    'Network %s RX bytes/sec' % (iface),
                    rx_bytes, prefix='%s.rx_bytes' % iface,
                    aggregation=Counter64),
                self.createEvent('ok',
                    'Network %s RX packets/sec' % (iface),
                    rx_packets, prefix='%s.rx_packets' % iface,
                    aggregation=Counter64),
                self.createEvent('ok',
                    'Network %s RX errors/sec' % (iface),
                    rx_err, prefix='%s.rx_errors' % iface,
                    aggregation=Counter64),
            ])

        return ev
