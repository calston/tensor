"""
.. module:: nginx
   :platform: Unix
   :synopsis: A source module for nginx stats

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time
import csv
from base64 import b64encode

from twisted.internet import defer

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.utils import HTTPRequest, fork
from tensor.aggregators import Counter

class HAProxy(Source):
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

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)
        
        self.url = self.config.get('url', 'http://localhost/haproxy?stats;csv')
        self.user = self.config.get('user', 'haproxy')
        self.password = self.config.get('password', 'stats')

    def _ev(self, val, desc, pref, aggr=True):
        if val:
            val = int(val)
            if aggr:
                aggr = Counter
            else:
                aggr = None

            return self.createEvent('ok',
                '%s: %s' % (desc, val), val, prefix=pref, aggregation=aggr)

    @defer.inlineCallbacks
    def get(self):
        url = self.config.get('url', self.config.get('stats_url'))

        authorization = b64encode('%s:%s' % (self.user, self.password))

        body = yield HTTPRequest().getBody(self.url,
            headers={
                'User-Agent': ['Tensor'],
                'Authorization': ['Basic ' + authorization]
            }
        )

        body = body.lstrip('# ').split('\n')

        events = []

        c = csv.DictReader(body, delimiter=',')
        for row in c:
            if row['svname'] == 'BACKEND':
                p = 'backends.%s' % row['pxname']

                events.append(self._ev(row['act'], 'Active servers',
                    '%s.active' % p))

            elif row['svname'] == 'FRONTEND':
                p = 'frontends.%s' % row['pxname']

            else:
                p = 'nodes.%s' % row['pxname']

                events.append(self._ev(row['chkfail'], 'Check failures',
                    '%s.checks_failed' % p))

            # Sessions
            events.extend([
                self._ev(row['scur'], 'Sessions',
                    '%s.sessions' % p, False),
                self._ev(row['stot'], 'Session rate',
                    '%s.session_rate' % p),
                self._ev(row['ereq'], 'Request errors',
                    '%s.errors_req' % p),
                self._ev(row['econ'], 'Backend connection errors',
                    '%s.errors_con' % p),
                self._ev(row['eresp'], 'Response errors',
                    '%s.errors_resp' % p),
                self._ev(row['wretr'], 'Retries',
                    '%s.retries' % p),
                self._ev(row['wredis'], 'Switches',
                    '%s.switches' % p),
                self._ev(int(row['bin'])*8, 'Bytes in',
                    '%s.bytes_in' % p),
                self._ev(int(row['bout'])*8, 'Bytes out',
                    '%s.bytes_out' % p),
                self._ev(row['hrsp_1xx'], '1xx codes',
                    '%s.code_1xx' % p),
                self._ev(row['hrsp_2xx'], '2xx codes',
                    '%s.code_2xx' % p),
                self._ev(row['hrsp_3xx'], '3xx codes',
                    '%s.code_3xx' % p),
                self._ev(row['hrsp_4xx'], '4xx codes',
                    '%s.code_4xx' % p),
                self._ev(row['hrsp_5xx'], '5xx codes',
                    '%s.code_5xx' % p),
            ])

        defer.returnValue([e for e in events if e])

