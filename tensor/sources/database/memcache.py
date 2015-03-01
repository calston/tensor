"""
.. module:: memcache
   :platform: Unix
   :synopsis: A source module for memcache stats

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time
import exceptions

from twisted.internet import defer
from twisted.internet import reactor, protocol
from twisted.protocols.memcache import MemCacheProtocol
from twisted.python import log

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.aggregators import Counter64

class Memcache(Source):
    """Reads memcache metrics

    **Configuration arguments:**
    
    :param host: Database host (default localhost)
    :type host: str.
    :param port: Database port (default 11211)
    :type port: int.

    **Metrics:**

    :(service name).(metrics): Metrics from memcached
    """

    implements(ITensorSource)

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 11211)

    @defer.inlineCallbacks
    def get(self):
        events = []
        try:
            memcache = yield protocol.ClientCreator(reactor, MemCacheProtocol
                        ).connectTCP(self.host, self.port)
            events.append(self.createEvent('ok', 'Connection', 1,
                prefix='state'))
        except:
            memcache = None
            events.append(self.createEvent('critical', 'Connection refused', 0,
                prefix='state'))

        if memcache:
            stats = yield memcache.stats()

            yield memcache.transport.loseConnection()

            counters = [
                'reclaimed', 'evictions', 'total_items',
                'touch_hits', 'touch_misses',
                'delete_misses', 'delete_hits',
                'incr_hits', 'incr_misses',
                'cas_hits', 'cas_misses', 'cas_badval',
                'get_misses', 'get_hits',
                'decr_misses', 'decr_hits',
                'cmd_set', 'cmd_flush', 'cmd_touch', 'cmd_get',
                'bytes_written', 'bytes_read',
            ]

            vals = ['curr_connections', 'curr_items', 'hash_bytes', 'bytes']

            for key in counters:
                d = key.capitalize().replace('_', ' ')
                s = key.replace('_', '.')
                events.append(self.createEvent('ok',
                    d, int(stats[key]), prefix=s, aggregation=Counter64))

            for key in vals:
                d = key.capitalize().replace('_', ' ')
                s = key.replace('_', '.')

                events.append(self.createEvent('ok', d, int(stats[key]),
                    prefix=s))

        defer.returnValue(events)
