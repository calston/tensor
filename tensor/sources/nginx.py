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
from tensor.aggregators import Counter64
from tensor.logs import parsers, follower

class Nginx(Source):
    """Reads Nginx stub_status

    **Configuration arguments:**
    
    :stats_url: URL to fetch stub_status from
    :type stats_url: str.

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
            'accepts': (float(accepts), Counter64),
            'requests': (float(requests), Counter64),
            'handled': (float(handled), Counter64),
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

class NginxLogMetrics(Source):
    """Tails Nginx log files, parses them and returns metrics for data usage
    and requests against other fields.

    **Configuration arguments:**
    
    :log_format: Log format passed to parser, same as the config definition
    :type log_format: str.
    :file: Log file
    :type file: str.

    **Metrics:**

    """

    implements(ITensorSource)

    # Don't allow overlapping runs
    sync = True

    def __init__(self, *a):
        Source.__init__(self, *a)

        parser = parsers.ApacheLogParser(self.config.get('log_format', 'combined'))

        self.log = follower.LogFollower(self.config['file'], parser=parser.parse)

        self.bucket = 0

    def _aggregate_fields(self, d, row, b, field, fil=None):
        f = row.get(field, None)

        if f:
            if fil:
                f = fil(f)
            if not (field in d):
                d[field] = {}

            if not (f in d[field]):
                d[field][f] = [b, 1]
            
            else:
                d[field][f][0] += b
                d[field][f][1] += 1

    def dumpEvents(self, ts):
        if self.st:
            events = [
                self.createEvent('ok', 'Nginx bytes', self.bytes, prefix='bytes',
                    evtime=ts),
                self.createEvent('ok', 'Nginx requests', self.requests,
                    prefix='requests', evtime=ts)
            ]

            for field, block in self.st.items():
                for key, vals in block.items():
                    bytes, requests = vals
                    events.extend([
                        self.createEvent('ok', 'Nginx %s %s bytes' % (field, key), bytes,
                            prefix='%s.%s.bytes' % (field, key), evtime=ts),
                        self.createEvent('ok', 'Nginx %s %s requests' % (field, key), requests,
                            prefix='%s.%s.requests' % (field, key), evtime=ts)
                    ])

            self.st = {}
            self.bytes = 0
            self.requests = 0

            self.queueBack(events)

    def got_line(self, line):
        b = line.get('bytes', 0)
        if b:
            self.bytes += b
        
        self.requests += 1

        t = time.mktime(line['time'].timetuple())

        bucket = (int(t)/10)*10

        if self.bucket:
            if (bucket != self.bucket):
                self.dumpEvents(float(self.bucket))
                self.bucket = bucket
        else:
            self.bucket = bucket

        self._aggregate_fields(self.st, line, b, 'status')
        self._aggregate_fields(self.st, line, b, 'client')
        self._aggregate_fields(self.st, line, b, 'user-agent',
            fil=lambda l: l.replace('.',',')
        )
        self._aggregate_fields(self.st, line, b, 'request',
            fil=lambda l: l.split()[1].split('?')[0].replace('.',',')
        )

    def get(self):
        self.bytes = 0
        self.requests = 0
        self.st = {}

        self.log.get_fn(self.got_line)

        self.dumpEvents(float(self.bucket))
