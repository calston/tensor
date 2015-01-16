import time

from twisted.internet import defer

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork


class DarwinRTSP(Source):
    """Makes avprobe requests of a Darwin RTSP sample stream
    (sample_100kbit.mp4)

    **Configuration arguments:**

    :param destination: Host name or IP address to check
    :type method: str.

    **Metrics:**
    :(service name): Time to complete request

    You can also override the `hostname` argument to make it match
    metrics from that host.
    """

    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        host = self.config.get('destination', self.hostname)

        t0 = time.time()
        try:
            out, err, code = yield fork('/usr/bin/avprobe',
                args=('rtsp://%s/sample_100kbit.mp4' % host, ), timeout=30.0)
        except:
            code = 1
            err = None

        t_delta = (time.time() - t0) * 1000

        if code == 0:
            e = self.createEvent('ok', 'RTSP Request time to %s' % host, 
                    t_delta)
        else:
            if err:
                try:
                    error = err.strip('\n').split('\n')[-2]
                except:
                    error = err.replace('\n', '-')
            else:
                error = "Execution error"

            e = self.createEvent('critical', 
                    'Unable to stream %s:%s' % (host, error),
                    t_delta)

        defer.returnValue(e)

