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
from tensor.protocol import icmp

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
            ip = yield reactor.resolve(host)
        except:
            ip = None

        if ip:
            try:
                loss, latency = yield icmp.ping(ip, 5)
            except: 
                loss, latency = 100, None

            event = [self.createEvent('ok', '%s%% loss to %s' % (loss,host), loss,
                prefix="loss")]

            if latency:
                event.append(self.createEvent('ok', 'Latency to %s' % host, latency,
                            prefix="latency"))
        else:
            event = [self.createEvent('critical', 'Unable to resolve %s' % host, 100,
                prefix="loss")]

        defer.returnValue(event)
