import os

from zope.interface import implements

from twisted.internet import defer

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork

class Sensors(Source):
    """Returns lm-sensors output

    NB. This is very untested on different configurations and versions. Please
    report any issues with the output of the `sensors` command to help
    improve it.

    **Metrics:**

    :(service name).(adapter).(sensor): Sensor value
    """
    implements(ITensorSource)


    @defer.inlineCallbacks
    def _get_sensors(self):
        out, err, code = yield fork('/usr/bin/sensors')
        if code == 0:
            defer.returnValue(out.strip('\n').split('\n'))
        else:
            defer.returnValue([])

    def _parse_sensors(self, sensors):
        adapters = {}
        adapter = None
        for i in sensors:
            l = i.strip()
            if not l:
                continue

            if ':' in l:
                n, v = l.split(':')
                vals = v.strip().split()

                if n=='Adapter':
                    continue

                if '\xc2\xb0' in vals[0]:
                    val = vals[0].split('\xc2\xb0')[0]
                    unit = vals[0][-1]
                elif len(vals)>1:
                    val = vals[0]
                    unit = vals[1]
                else:
                    continue

                val = float(val)

                adapters[adapter][n] = val

            else:
                adapter = l
                adapters[adapter] = {}
        
        return adapters

    @defer.inlineCallbacks
    def get(self):
        sensors = yield self._get_sensors()
        adapters = self._parse_sensors(sensors)

        events = []

        for adapter, v in adapters.items():
            for sensor, val in v.items():
                events.append(
                    self.createEvent('ok',
                        'Sensor %s:%s - %s' % (adapter, sensor, val),
                        val,
                        prefix='%s.%s' % (adapter, sensor,)))
        
        defer.returnValue(events)

class SMART(Source):
    """Returns SMART output for all disks

    **Metrics:**

    :(service name).(disk).(sensor): Sensor value
    """
    implements(ITensorSource)

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        self.devices = []

    @defer.inlineCallbacks
    def _get_disks(self):
        out, err, code = yield fork('/usr/sbin/smartctl',
            args=('--scan',))

        if code != 0:
            defer.returnValue([])

        out = out.strip('\n').split('\n')
        devices = []
        for ln in out:
            if '/dev' in ln:
                devices.append(ln.split()[0])

        defer.returnValue(devices)

    @defer.inlineCallbacks
    def _get_smart(self, device):
        out, err, code = yield fork('/usr/sbin/smartctl',
            args=('-A', device))

        if code == 0:
            defer.returnValue(out.strip('\n').split('\n'))
        else:
            defer.returnValue([])

    def _parse_smart(self, smart):
        mark = False
        attributes = {}
        for l in smart:
            ln = l.strip('\n').strip()
            if not ln:
                continue

            if mark:
                (id, attribute, flag, val, worst,thresh, type, u, wf, raw
                    ) = ln.split(None, 9)

                try:
                    raw = int(raw.split()[0])
                    attributes[attribute.replace('_', ' ')] = raw
                except:
                    pass

            if ln[:3] == 'ID#':
                mark = True
        
        return attributes

    @defer.inlineCallbacks
    def get(self):
        disks = self._get_disks()

        if not self.devices:
            self.devices = yield self._get_disks()

        events = []

        for disk in self.devices:
            smart = yield self._get_smart(disk)
            stats = self._parse_smart(smart)

            for sensor, val in stats.items():
                events.append(
                    self.createEvent('ok',
                        'Attribute %s:%s - %s' % (disk, sensor, val),
                        val,
                        prefix='%s.%s' % (disk, sensor,)))
        
        defer.returnValue(events)
