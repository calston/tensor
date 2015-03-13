import time
import json

from twisted.internet import reactor, defer, task
from twisted.python import log

try:
    from OpenSSL import SSL
    from twisted.internet import ssl
except:
    SSL=None

from tensor.protocol import elasticsearch

from tensor.objects import Output

class ElasticSearchLog(Output):
    """ElasticSearch HTTP API output

    This Output transposes events to a Logstash format

    **Configuration arguments:**

    :param server: Elasticsearch server
    :type server: str
    :param port: Elasticsearch server port (default: 9200)
    :type port: int
    :param maxsize: Maximum queue backlog size (default: 250000, 0 disables)
    :type maxsize: int
    :param maxrate: Maximum rate of documents added to index (default: 100)
    :type maxrate: int
    :param interval: Queue check interval in seconds (default: 1.0)
    :type interval: int
    """
    def __init__(self, *a):
        Output.__init__(self, *a)
        self.events = []
        self.t = task.LoopingCall(self.tick)

        self.inter = float(self.config.get('interval', 1.0))  # tick interval
        self.maxsize = int(self.config.get('maxsize', 250000))

        maxrate = int(self.config.get('maxrate', 100))

        if maxrate > 0:
            self.queueDepth = int(maxrate * self.inter)
        else:
            self.queueDepth = None

    def createClient(self):
        """Create a TCP connection to Riemann with automatic reconnection
        """

        server = self.config.get('server', 'localhost')
        port = int(self.config.get('port', 9200))

        self.client = elasticsearch.ElasticSearch(host=server, port=port)

        self.t.start(self.inter)

    def stop(self):
        """Stop this client.
        """
        self.t.stop()

    def transposeEvent(self, event):
        d = event.description
        d['type'] = event.service
        d['host'] = event.hostname
        d['tags'] = event.tags

        if event._type=='log':
            return d

        return None

    def sendEvents(self, events):
        for i, e in enumerate(events):
            events[i] = self.transposeEvent(e)

        return self.client.bulkIndex(events)

    @defer.inlineCallbacks
    def tick(self):
        """Clock tick called every self.inter
        """
        if self.events:
            if self.queueDepth:
                # Remove maximum of self.queueDepth items from queue
                events = self.events[:self.queueDepth]
                self.events = self.events[self.queueDepth:]
            else:
                events = self.events
                self.events = []

            result = yield self.sendEvents(events)

            if result.get('errors', False):
                log.msg(repr(result))

    def eventsReceived(self, events):
        """Receives a list of events and queues them

        Arguments:
        events -- list of `tensor.objects.Event`
        """
        # Make sure queue isn't oversized
        if (self.maxsize < 1) or (len(self.events) < self.maxsize):
            self.events.extend(events)

