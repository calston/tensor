from twisted.internet import reactor, defer
from tensor.protocol import riemann

from tensor.objects import Output


class RiemannTCP(Output):
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
                d.callback(None)
            else:
                reactor.callLater(0.01, cb)

        cb()

        return d

    def eventsReceived(self, events):
        """Receives a list of events and transmits them to Riemann

        Arguments:
        events -- list of `tensor.objects.Event`
        """

        self.protocol.sendEvents(events)

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

