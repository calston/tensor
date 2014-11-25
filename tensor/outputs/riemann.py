import time

from twisted.internet import reactor, defer, task
from tensor.protocol import riemann

from tensor.objects import Output


class RiemannTCP(Output):
    def __init__(self, *a):
        Output.__init__(self, *a)
        self.events = []
        self.t = task.LoopingCall(self.tick)

        self.inter = float(self.config.get('interval', 1.0))  # tick interval
        self.pressure = int(self.config.get('pressure', -1))

        maxrate = int(self.config.get('maxrate', 0))

        if maxrate > 0:
            self.queueDepth = int(maxrate * self.inter)
        else:
            self.queueDepth = None

    def createClient(self):
        """Create a TCP connection to Riemann with automatic reconnection
        """
        self.factory = riemann.RiemannClientFactory()

        server = self.config.get('server', 'localhost')
        port = self.config.get('port', 5555)

        self.connector = reactor.connectTCP(server, port, self.factory)

        d = defer.Deferred()

        def cb():
            # Wait until we have a useful proto object
            if hasattr(self.factory, 'proto') and self.factory.proto:
                self.t.start(self.inter)
                d.callback(None)
            else:
                reactor.callLater(0.01, cb)

        cb()

        return d

    def stop(self):
        """Stop this client.
        """
        self.t.stop()
        self.factory.stopTrying()
        self.connector.disconnect()

    def tick(self):
        """Clock tick called every self.inter
        """
        if self.factory.proto:
            # Check backpressure
            if (self.pressure < 0) or (self.factory.proto.pressure <= self.pressure):
                self.emptyQueue()
        else:
            # Check queue age and expire stale events
            for i, e in enumerate(self.events):
                if (time.time() - e.time) > e.ttl:
                    self.events.pop(i)

    def emptyQueue(self):
        """Remove all or self.queueDepth events from the queue
        """
        if self.events:
            if self.queueDepth:
                # Remove maximum of self.queueDepth items from queue
                events = self.events[:self.queueDepth]
                self.events = self.events[self.queueDepth:]
            else:
                events = self.events
                self.events = []

            self.factory.proto.sendEvents(events)

    def eventsReceived(self, events):
        """Receives a list of events and transmits them to Riemann

        Arguments:
        events -- list of `tensor.objects.Event`
        """

        self.events.extend(events)

class RiemannUDP(Output):
    def __init__(self, *a):
        Output.__init__(self, *a)
        self.protocol = None

    def createClient(self):
        """Create a UDP connection to Riemann"""
        server = self.config.get('server', '127.0.0.1')
        port = self.config.get('port', 5555)

        def connect(ip):
            self.protocol = riemann.RiemannUDP(ip, port)
            self.endpoint = reactor.listenUDP(0, self.protocol)

        d = reactor.resolve(server)
        d.addCallback(connect)
        return d

    def eventsReceived(self, events):
        """Receives a list of events and transmits them to Riemann

        Arguments:
        events -- list of `tensor.objects.Event`
        """
        if self.protocol:
            self.protocol.sendEvents(events)

