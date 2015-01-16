"""
.. module:: riak
   :platform: Any
   :synopsis: A source module for Riak metrics

.. moduleauthor:: Jeremy Thurgood <firxen@gmail.com>
"""

import json

from twisted.internet import defer, reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.utils import BodyReceiver


class RiakStats(Source):
    """Returns GET/PUT rates for a Riak node

    **Configuration arguments:**

    :param url: Riak stats URL
    :type url: str.
    :param useragent: User-Agent header to use
    :type useragent: str.

    **Metrics:**

    :(service name).latency: Time to complete request
    """

    implements(ITensorSource)

    @defer.inlineCallbacks
    def _get_stats_from_node(self):
        agent = Agent(reactor)

        url = self.config.get('url', 'http://%s:8098/stats' % self.hostname)
        ua = self.config.get('useragent', 'Tensor Riak stats checker')

        headers = Headers({'User-Agent': [ua]})
        request = yield agent.request('GET', url, headers)

        if request.length:
            d = defer.Deferred()
            request.deliverBody(BodyReceiver(d))
            b = yield d
            body = b.read()
        else:
            body = ""

        defer.returnValue(json.loads(body))

    @defer.inlineCallbacks
    def get(self):
        stats = yield self._get_stats_from_node()
        get_rate = stats['node_gets'] / 60.0
        put_rate = stats['node_puts'] / 60.0

        defer.returnValue([
            self.createEvent(
                'ok', 'GETs per second for past minute', get_rate,
                prefix="gets_per_second"),
            self.createEvent(
                'ok', 'PUTs per second for past minute', put_rate,
                prefix="puts_per_second"),
        ])
