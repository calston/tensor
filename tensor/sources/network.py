"""
.. module:: network
   :platform: Unix
   :synopsis: A source module for network checks

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time

from twisted.internet import defer, reactor
from twisted.python import log

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.utils import fork, HTTPRequest, Timeout

class HTTP(Source):
    """Performs an HTTP request

    **Configuration arguments:**
    
    :param url: HTTP URL
    :type url: str.
    :param method: HTTP request method to use (default GET)
    :type method: str.
    :param match: A text string to match in the document when it is correct
    :type match: str.
    :param useragent: User-Agent header to use
    :type useragent: str.
    :param timeout: Timeout for connection (default 60s)
    :type timeout: int.

    **Metrics:**

    :(service name).latency: Time to complete request
    """

    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):

        method = self.config.get('method', 'GET')
        url = self.config.get('url', 'http://%s/' % self.hostname)
        match = self.config.get('match', None)
        ua = self.config.get('useragent', 'Tensor HTTP checker')
        timeout = self.config.get('timeout', 60)

        t0 = time.time()

        try:
            body = yield HTTPRequest(timeout).getBody(url, method,
                {'User-Agent': [ua]},
            )
        except Timeout:
            log.msg('[%s] Request timeout' % url)
            t_delta = (time.time() - t0) * 1000
            defer.returnValue(
                self.createEvent('critical', '%s - timeout' % url, t_delta,
                    prefix="latency")
            )
        except Exception, e:
            log.msg('[%s] Request error %s' % (url, e))
            t_delta = (time.time() - t0) * 1000
            defer.returnValue(
                self.createEvent('critical', '%s - %s' % (url, e), t_delta,
                    prefix="latency")
            )

        t_delta = (time.time() - t0) * 1000

        if match:
            if (match in body):
                state = 'ok'
            else:
                state = 'critical'
        else:
            state = 'ok'
        
        defer.returnValue(
            self.createEvent(state, 'Latency to %s' % url, t_delta,
                prefix="latency")
        )

class Ping(Source):
    """Performs an Ping checks against a destination

    This is a horrible implementation which forks to `ping`

    **Configuration arguments:**
    
    :param destination: Host name or IP address to ping
    :type destination: str.

    **Metrics:**

    :(service name).latency: Ping latency
    :(service name).loss: Packet loss

    You can also override the `hostname` argument to make it match
    metrics from that host.
    """

    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        host = self.config.get('destination', self.hostname)


        try:
            out, err, code = yield fork('/bin/ping',
                args=('-q', '-n', '-c', '5', '-i', '0.2', host), timeout=30.0)
        except:
            code = 1

        if code == 0:
            # Successful ping
            try:
                out = out.strip('\n').split('\n')[-2:]
                loss = int(out[0].split()[5].strip('%'))

                stat = out[1].split()[3].split('/')
                pmin, avg, pmax, mdev = [float(i) for i in stat]

                event = [
                    self.createEvent('ok', 'Latency to %s' % host, avg,
                        prefix="latency"),
                    self.createEvent('ok', '%s%% loss to %s' % (loss,host), loss,
                        prefix="loss"),
                ]
            except Exception, e:
                print("Could not parse response %s" % repr(out))
                event = None

        elif code == 1:
            # Host unreachable
            event = self.createEvent('critical', '100%% loss to %s' % host, 100.0,
                    prefix="loss")
        else:
            # Some other kind of error like DNS resolution
            event = self.createEvent('critical', 'Unable to reach %s' % host, 100.0,
                    prefix="loss")

        defer.returnValue(event)

