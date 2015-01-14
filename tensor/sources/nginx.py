"""
.. module:: nginx
   :platform: Unix
   :synopsis: A source module for nginx stats

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time

from twisted.internet import defer, reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.utils import BodyReceiver, fork
from tensor.aggregators import Counter

class Nginx(Source):
    """Reads Nginx stub_status

    **Configuration arguments:**
    
    :stats_url: URL to fetch stub_status from
    :type method: str.

    **Metrics:**

    :(service name).active: Active connections at this time
    :(service name).accepts: Accepted connections
    :(service name).handled: Handled connections
    :(service name).requests: Total client requests
    :(service name).reading: Reading requests
    :(service name).writing: Writing responses
    :(service name).waiting: Waiting connections
    """

    implements(ITensorSource)

    def _parse_nginx_stats(self, stats):
        stats = stats.split('\n')
        active = stats[0].split(': ')[-1]

        accepts, handled, requests = stats[2].split()

        _, reading, _, writing, _, waiting = stats[3].split()

        metrics = {
            'active': (float(active), None),
            'accepts': (float(accepts), Counter),
            'requests': (float(requests), Counter),
            'handled': (float(handled), Counter),
            'reading': (float(reading), None),
            'writing': (float(writing), None),
            'waiting': (float(waiting), None),
        }

        return metrics

    @defer.inlineCallbacks
    def get(self):
        agent = Agent(reactor)

        url = self.config.get('url', self.config.get('stats_url'))

        t0 = time.time()

        request = yield agent.request('GET', url,
            Headers({'User-Agent': ['Tensor']}),
        )

        events = []

        if request.length:
            d = defer.Deferred()
            request.deliverBody(BodyReceiver(d))
            b = yield d
            body = b.read()

            metrics = self._parse_nginx_stats(body)

            for k,v in metrics.items():
                metric, aggr = v
                events.append(
                    self.createEvent('ok', 'Nginx %s' % (k), metric, prefix=k,
                        aggregation=aggr)
                )
            
        defer.returnValue(events)
