from twisted.internet import defer, utils

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

class Ping(Source):
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        host = self.config.get('destination', self.hostname)

        out, err, code = yield utils.getProcessOutputAndValue('/bin/ping',
            args=('-q', '-n', '-c', '5', '-i', '0.2', host))

        if code == 0:
            # Successful ping
            out = out.strip('\n').split('\n')[-2:]
            loss = int(out[0].split()[5].strip('%'))

            stat = out[1].split()[-2].split('/')
            pmin, avg, pmax, mdev = [float(i) for i in stat]

            event = [
                self.createEvent('ok', 'Latency to %s' % host, avg,
                    prefix="latency"),
                self.createEvent('ok', '%s%% loss to %s' % (loss,host), loss,
                    prefix="loss"),
            ]

        elif code == 1:
            # Host unreachable
            event = self.createEvent('critical', '100%% loss to %s' % host, 100.0,
                    prefix="loss")
        else:
            # Some other kind of error like DNS resolution
            event = self.createEvent('critical', 'Unable to reach %s' % host, 100.0,
                    prefix="loss")

        defer.returnValue(event)

