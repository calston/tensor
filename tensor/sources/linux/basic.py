import time

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
    """Reports disk IO statistics per device

    **Configuration arguments:**

    :param devices: List of devices to check (optional)
    :type devices: list.

    **Metrics:**

    :(service name).(device name).reads: Number of completed reads
    :(service name).(device name).read_bytes: Bytes read per second
    :(service name).(device name).read_latency: Disk read latency
    :(service name).(device name).writes: Number of completed writes
    :(service name).(device name).write_bytes: Bytes written per second
    :(service name).(device name).write_latency: Disk write latency
    """

    implements(ITensorSource)

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        self.devices = self.config.get('devices')

        self.tcache = {}
        self.trc = {}
        self.twc = {}

    def _getstats(self):
        stats = open('/proc/diskstats', 'rt').read()

        return stats.strip('\n').split('\n')

    def get(self):
        disks = {}
        events = []

        stats = self._getstats()


        for s in stats:
            parts = s.strip().split()
            n = parts[2]
            # Filter things we don't care about
            if (n[:4] != 'loop') and (n[:3] != 'ram'):
                dname = "/dev/" + n

                if self.devices and (dname not in self.devices):
                    continue
                
                nums = [int(i) for i in parts[3:]]

                reads, read_m, read_sec, read_t = nums[:4]
                writes, write_m, write_sec, write_t = nums[4:8]
                cur_io, io_t, io_wt = nums[8:]

                # Calculate the average latency of read/write ops
                if n in self.tcache:
                    (last_r, last_w, last_rt, last_wt) = self.tcache[n]

                    r_delta = float(reads - last_r)
                    w_delta = float(writes - last_w)

                    if r_delta > 0:
                        read_lat = (read_t - last_rt)/float(reads - last_r)
                        self.trc[n] = read_lat
                    else:
                        read_lat = self.trc.get(n, None)

                    if w_delta > 0:
                        write_lat = (write_t - last_wt)/float(writes - last_w)
                        self.twc[n] = write_lat
                    else:
                        write_lat = self.twc.get(n, None)

                else:
                    if reads > 0:
                        read_lat = read_t / float(reads)
                        self.trc[n] = read_lat
                    else:
                        read_lat = None

                    if writes > 0:
                        write_lat = write_t / float(writes)
                        self.twc[n] = write_lat
                    else:
                        write_lat = None

                self.tcache[n] = (reads, writes, read_t, write_t)

                if read_lat:
                     events.append(self.createEvent('ok',
                        'Read latency (ms)', read_lat,
                        prefix='%s.read_latency' % dname))

                if write_lat:
                     events.append(self.createEvent('ok',
                        'Write latency (ms)', write_lat,
                        prefix='%s.write_latency' % dname))

                events.extend([
                    self.createEvent('ok', 'Reads' , reads,
                        prefix='%s.reads' % dname, aggregation=Counter64),
                    self.createEvent('ok', 'Read Bps' , read_sec * 512,
                        prefix='%s.read_bytes' % dname, aggregation=Counter64),

                    self.createEvent('ok', 'Writes', writes,
                        prefix='%s.writes' % dname, aggregation=Counter64),
                    self.createEvent('ok', 'Write Bps', write_sec * 512,
                        prefix='%s.write_bytes' % dname, aggregation=Counter64),
                ])

        return events


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

    **Configuration arguments:**

    :param disks: List of devices to check (optional)
    :type disks: list.

    **Metrics:**

    :(service name).(device): Used space (%)
    :(service name).(device).bytes: Used space (kbytes)
    :(service name).(device).free: Free space (kbytes)
    """
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        disks = self.config.get('disks')

        out, err, code = yield fork('/bin/df', args=('-lPx', 'tmpfs',))

        out = [i.split() for i in out.strip('\n').split('\n')[1:]]

        events = []

        for disk, size, used, free, util, mount in out:
            if disks and (disk not in disks):
                continue

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

    **Configuration arguments:**

    :param interfaces: List of interfaces to check (optional)
    :type interfaces: list.

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
        ifaces = self.config.get('interfaces')

        ev = []

        for stat in self._readStats():
            items = stat.split()
            iface = items[0].strip(':')

            if ifaces and (iface not in ifaces):
                continue

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
