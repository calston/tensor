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

    :param url: Elasticsearch URL (default: http://localhost:9200)
    :type url: str
    :param maxsize: Maximum queue backlog size (default: 250000, 0 disables)
    :type maxsize: int
    :param maxrate: Maximum rate of documents added to index (default: 100)
    :type maxrate: int
    :param interval: Queue check interval in seconds (default: 1.0)
    :type interval: int
    :param user: Optional basic auth username
    :type user: str
    :param password: Optional basic auth password
    :type password: str
    """
    def __init__(self, *a):
        Output.__init__(self, *a)
        self.events = []
        self.t = task.LoopingCall(self.tick)

        self.inter = float(self.config.get('interval', 1.0))  # tick interval
        self.maxsize = int(self.config.get('maxsize', 250000))

        self.user = self.config.get('user')
        self.password = self.config.get('password')

        self.url = self.config.get('url', 'http://localhost:9200')

        maxrate = int(self.config.get('maxrate', 100))

        if maxrate > 0:
            self.queueDepth = int(maxrate * self.inter)
        else:
            self.queueDepth = None

    def createClient(self):
        """Sets up HTTP connector and starts queue timer
        """

        server = self.config.get('server', 'localhost')
        port = int(self.config.get('port', 9200))

        self.client = elasticsearch.ElasticSearch(self.url, self.user,
            self.password)

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
        return self.client.bulkIndex(
            [self.transposeEvent(e) for e in events])

    @defer.inlineCallbacks
    def tick(self):
        """Clock tick called every self.inter
        """
        if self.events:
            if self.queueDepth and (len(self.events) > self.queueDepth):
                # Remove maximum of self.queueDepth items from queue
                events = self.events[:self.queueDepth]
                self.events = self.events[self.queueDepth:]
            else:
                events = self.events
                self.events = []

            try:
                result = yield self.sendEvents(events)
                if result.get('errors', False):
                    log.msg(repr(result))
                    self.events.extend(events)

            except Exception, e:
                log.msg('Could not connect to elasticsearch ' + str(e))
                self.events.extend(events)

    def eventsReceived(self, events):
        """Receives a list of events and queues them

        Arguments:
        events -- list of `tensor.objects.Event`
        """
        # Make sure queue isn't oversized
        if (self.maxsize < 1) or (len(self.events) < self.maxsize):
            self.events.extend(events)

