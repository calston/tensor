import time

from twisted.internet import defer, utils

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source


class DarwinRTSP(Source):
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        host = self.config.get('destination', self.hostname)

        t0 = time.time()
        out, err, code = yield utils.getProcessOutputAndValue('/usr/bin/avprobe',
            args=('rtsp://%s/sample_100kbit.mp4' % host, ))

        t_delta = (time.time() - t0) * 1000

        if code == 0:
            e = self.createEvent('ok', 'RTSP Request time to %s' % host, 
                    t_delta)
        else:
            error = err.strip('\n').split('\n')[-2]
            e = self.createEvent('critical', 
                    'Unable to stream %s:%s' % (host, error),
                    t_delta)

        defer.returnValue(e)

