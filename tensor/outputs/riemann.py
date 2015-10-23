import time
import random

from twisted.internet import reactor, defer, task
from twisted.python import log

try:
    from OpenSSL import SSL
    from twisted.internet import ssl
except:
    SSL=None

from tensor.protocol import riemann

from tensor.objects import Output

if SSL:
    class ClientTLSContext(ssl.ClientContextFactory):
        def __init__(self, key, cert):
            self.key = key
            self.cert = cert

        def getContext(self):
            self.method = SSL.TLSv1_METHOD
            ctx = ssl.ClientContextFactory.getContext(self)
            ctx.use_certificate_file(self.cert)
            ctx.use_privatekey_file(self.key)

            return ctx

class RiemannTCP(Output):
    """Riemann TCP output

    **Configuration arguments:**

    :param server: Riemann server hostname (default: localhost)
    :type server: str.
    :param port: Riemann server port (default: 5555)
    :type port: int.
    :param failover: Enable server failover, in which case `server` may be a list
    :type failover: bool.
    :param maxrate: Maximum de-queue rate (0 is no limit)
    :type maxrate: int.
    :param maxsize: Maximum queue size (0 is no limit, default is 250000)
    :type maxsize: int.
    :param interval: De-queue interval in seconds (default: 1.0)
    :type interval: float.
    :param pressure: Maximum backpressure (-1 is no limit)
    :type pressure: int.
    :param tls: Use TLS (default false)
    :type tls: bool.
    :param cert: Host certificate path
    :type cert: str.
    :param key: Host private key path
    :type key: str.
    :param allow_nan: Send events with None metric value (default true)
    :type allow_nan: bool
    """
    def __init__(self, *a):
        Output.__init__(self, *a)
        self.events = []
        self.t = task.LoopingCall(self.tick)

        self.inter = float(self.config.get('interval', 1.0))  # tick interval
        self.pressure = int(self.config.get('pressure', -1))
        self.maxsize = int(self.config.get('maxsize', 250000))
        self.expire = self.config.get('expire', False)
        self.allow_nan = self.config.get('allow_nan', True)

        maxrate = int(self.config.get('maxrate', 0))

        if maxrate > 0:
            self.queueDepth = int(maxrate * self.inter)
        else:
            self.queueDepth = None

        self.tls = self.config.get('tls', False)

        if self.tls:
            self.cert = self.config['cert']
            self.key = self.config['key']

    def createClient(self):
        """Create a TCP connection to Riemann with automatic reconnection
        """

        server = self.config.get('server', 'localhost')
        port = self.config.get('port', 5555)
        failover = self.config.get('failover', False)

        self.factory = riemann.RiemannClientFactory(server, failover=failover)

        if failover:
            initial = random.choice(server)
        else:
            initial = server

        log.msg('Connecting to Riemann on %s:%s' % (initial, port))
        
        if self.tls:
            if SSL:
                self.connector = reactor.connectSSL(initial, port, self.factory,
                    ClientTLSContext(self.key, self.cert))
            else:
                log.msg('[FATAL] SSL support not available!' \
                    ' Please install PyOpenSSL. Exiting now')
                reactor.stop()
        else:
            self.connector = reactor.connectTCP(initial, port, self.factory)

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
        elif self.expire:
            # Check queue age and expire stale events
            for i, e in enumerate(self.events):
                if (time.time() - e.time) > e.ttl:
                    self.events.pop(i)

    def emptyQueue(self):
        """Remove all or self.queueDepth events from the queue
        """
        if self.events:
            if self.queueDepth and (len(self.events) > self.queueDepth):
                # Remove maximum of self.queueDepth items from queue
                events = self.events[:self.queueDepth]
                self.events = self.events[self.queueDepth:]
            else:
                events = self.events
                self.events = []

            if self.allow_nan:
                self.factory.proto.sendEvents(events)
            else:
                self.factory.proto.sendEvents([e for e in events if e.metric is not None])

    def eventsReceived(self, events):
        """Receives a list of events and transmits them to Riemann

        Arguments:
        events -- list of `tensor.objects.Event`
        """
        # Make sure queue isn't oversized
        if (self.maxsize < 1) or (len(self.events) < self.maxsize):
            self.events.extend(events)

class RiemannUDP(Output):
    """Riemann UDP output (spray-and-pray mode)

    **Configuration arguments:**

    :param server: Riemann server IP address (default: 127.0.0.1)
    :type server: str.
    :param port: Riemann server port (default: 5555)
    :type port: int.
    """

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

