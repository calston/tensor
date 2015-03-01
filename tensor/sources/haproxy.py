"""
.. module:: haproxy
   :platform: Unix
   :synopsis: A source module for haproxy stats

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
    
    :param url: URL to fetch stats from
    :type url: str.
    :param user: Username
    :type user: str.
    :param password: Password
    :type password: str.

    **Metrics:**

    :(service name).(backend|frontend|nodes).(stats): Various statistics
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

        events = []

        try:
            body = yield HTTPRequest().getBody(self.url,
                headers={
                    'User-Agent': ['Tensor'],
                    'Authorization': ['Basic ' + authorization]
                }
            )

            body = body.lstrip('# ').split('\n')

            events.append(self.createEvent('ok',
                'Connection ok', 1, prefix='state'))
        except Exception, e:
            defer.returnValue(self.createEvent('critical',
                'Connection failed: %s' % (str(e)), 0, prefix='state'))

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

