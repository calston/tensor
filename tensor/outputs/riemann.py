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
        self.protocol = None

    def createClient(self):
        """Create a TCP connection to Riemann with automatic reconnection
        """
        self.factory = riemann.RiemannClientFactory()

        server = self.config.get('server', 'localhost')
        port = self.config.get('port', 5555)

        reactor.connectTCP(server, port, self.factory)

        d = defer.Deferred()

        def cb():
            # Wait until we have a useful proto object
            if hasattr(self.factory, 'proto') and self.factory.proto:
                self.protocol = self.factory.proto
                self.t.start(self.inter)
                d.callback(None)
            else:
                reactor.callLater(0.01, cb)

        cb()

        return d

    def tick(self):
        if self.protocol:
            # Check backpressure
            if (self.pressure < 0) or (self.protocol.pressure <= self.pressure):
                self.emptyQueue()
        else:
            # Check queue age and expire stale events
            for i, e in enumerate(self.events):
                if (time.time() - e.time) > e.ttl:
                    self.events.pop(i)

    def emptyQueue(self):
        if self.events:
            events = self.events
            self.tensor.eventCounter += len(events)
            self.events = []

            self.protocol.sendEvents(events)

    def eventsReceived(self, events):
        """Receives a list of events and transmits them to Riemann

        Arguments:
        events -- list of `tensor.objects.Event`
        """

        self.events.extend(events)

class RiemannUDP(Output):
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

        self.protocol.sendEvents(events)

