"""
.. module:: elasticsearch
   :platform: Unix
   :synopsis: A source module for elasticsearch stats

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

from twisted.internet import defer
from twisted.python import log

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.aggregators import Counter64
from tensor.protocol import elasticsearch

class ElasticSearch(Source):
    """Reads elasticsearch metrics

    **Configuration arguments:**
    
    :param url: Elasticsearch base URL (default: http://localhost:9200)
    :type url: str.
    :param user: Basic auth username
    :type user: str.
    :param password: Password
    :type password: str.

    **Metrics:**

    :(service name).cluster.status: Cluster status (Red=0, Yellow=1, Green=2)
    :(service name).cluster.nodes: Cluster node count
    :(service name).indices: Total indices in cluster
    :(service name).shards.total: Total number of shards
    :(service name).shards.primary: Number of primary shards
    :(service name).documents.total: Total documents
    :(service name).documents.rate: Documents per second
    :(service name).documents.size: Size of document store in bytes
    """

    implements(ITensorSource)

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)
        self.url = self.config.get('url', 'http://localhost:9200').rstrip('\n')
        user = self.config.get('user')
        passwd = self.config.get('password')

        self.client = elasticsearch.ElasticSearch(self.url, user, passwd)

    @defer.inlineCallbacks
    def get(self):
        stats = yield self.client.stats()

        status = {'green': 2, 'yellow': 1, 'red': 0}[stats['status']]
    
        nodes = stats['nodes']['count']['total']
        index_count = stats['indices']['count']
        shards = stats['indices']['shards']['total']
        shards_primary = stats['indices']['shards']['primaries']

        docs = stats['indices']['docs']['count']
        store = stats['indices']['store']['size_in_bytes']

        defer.returnValue([
            self.createEvent('ok', 'Status', status, prefix='cluster.status'),
            self.createEvent('ok', 'Nodes', nodes, prefix='cluster.nodes'),
            self.createEvent('ok', 'Indices', index_count, prefix='indices'),
            self.createEvent('ok', 'Shards', shards, prefix='shards.total'),
            self.createEvent('ok', 'Primary shards', shards_primary, prefix='shards.primary'),

            self.createEvent('ok', 'Documents', shards_primary, prefix='documents.total'),
            self.createEvent('ok', 'Documents', shards_primary, prefix='documents.rate', aggregation=Counter64),
            self.createEvent('ok', 'Store size', store, prefix='documents.size'),
        ])
