"""
.. module:: nginx
   :platform: Unix
   :synopsis: A source module for nginx stats

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time

from twisted.internet import defer

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.utils import HTTPRequest, fork
from tensor.aggregators import Counter64
from tensor.logs import parsers, follower

class Nginx(Source):
    """Reads Nginx stub_status

    **Configuration arguments:**
    
    :param stats_url: URL to fetch stub_status from
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
        url = self.config.get('url', self.config.get('stats_url'))

        body = yield HTTPRequest().getBody(url,
            headers={'User-Agent': ['Tensor']},
        )

        events = []

        if body:
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
    
    :param log_format: Log format passed to parser, same as the config
                       definition
    :type log_format: str.
    :param file: Log file
    :type file: str.
    :param max_lines: Maximum number of log lines to read per interval to
                      prevent overwhelming Tensor when reading large logs
                      (default 2000)
    :type max_lines: int.
    :param resolution: Aggregate bucket resolution in seconds (default 10)
    :type resolution: int.
    :param history: Read the entire file from scratch if we've never seen
                    it (default false)
    :type history: bool.

    **Metrics:**

    :(service name).total_bytes: Bytes total for all requests
    :(service name).total_requests: Total request count
    :(service name).stats.(code).(requests|bytes): Metrics by status code
    :(service name).user-agent.(agent).(requests|bytes): Metrics by user agent
    :(service name).client.(ip).(requests|bytes): Metrics by client IP
    :(service name).request.(request path).(requests|bytes): Metrics by request path
    """

    implements(ITensorSource)

    # Don't allow overlapping runs
    sync = True

    def __init__(self, *a):
        Source.__init__(self, *a)

        parser = parsers.ApacheLogParser(self.config.get('log_format', 'combined'))

        history = self.config.get('history', False)

        self.log = follower.LogFollower(self.config['file'],
            parser=parser.parse, history=history)

        self.max_lines = int(self.config.get('max_lines', 2000))
        self.bucket_res = int(self.config.get('resolution', 10))

        self.bucket = 0

    def _aggregate_fields(self, row, b, field, fil=None):
        f = row.get(field, None)

        if f:
            if fil:
                f = fil(f)
            if not (field in self.st):
                self.st[field] = {}

            if not (f in self.st[field]):
                self.st[field][f] = [b, 1]
            
            else:
                self.st[field][f][0] += b
                self.st[field][f][1] += 1

    def dumpEvents(self, ts):
        if self.st:
            events = [
                self.createEvent('ok', 'Nginx bytes', self.bytes, prefix='total_bytes',
                    evtime=ts),
                self.createEvent('ok', 'Nginx requests', self.requests,
                    prefix='total_requests', evtime=ts)
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

        # Calculate the time bucket for this line
        bucket = (int(t)/self.bucket_res)*self.bucket_res

        if self.bucket:
            if (bucket != self.bucket):
                self.dumpEvents(float(self.bucket))
                self.bucket = bucket
        else:
            self.bucket = bucket

        self._aggregate_fields(line, b, 'status')
        self._aggregate_fields(line, b, 'client')
        self._aggregate_fields(line, b, 'user-agent',
            fil=lambda l: l.replace('.',',')
        )
        self._aggregate_fields(line, b, 'request',
            fil=lambda l: l.split()[1].split('?')[0].replace('.',',')
        )

    def get(self):
        self.bytes = 0
        self.requests = 0
        self.st = {}

        self.log.get_fn(self.got_line, max_lines=self.max_lines)

        self.dumpEvents(float(self.bucket))
