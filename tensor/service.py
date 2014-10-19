import time
import importlib

from twisted.application import service
from twisted.internet import task, reactor, defer

from tensor.protocol import riemann


class TensorService(service.Service):
    """ Tensor service
    
    Runs timers, configures sources and and manages the queue
    """
    def __init__(self, config):
        self.t = task.LoopingCall(self.tick)
        self.running = 0
        self.sources = []
        self.events = []

        self.factory = None

        # Read some config stuff
        self.inter = float(config['interval'])  # tick interval
        self.server = config.get('server', 'localhost')
        self.port = int(config.get('port', 5555))
        self.pressure = int(config.get('pressure', -1))
        self.ttl = float(config.get('ttl', 60.0))
        self.stagger = float(config.get('stagger', 0.2))

        self.setupSources(config)

    def connectClient(self):
        """Deferred which connects to Riemann"""
        self.factory = riemann.RiemannClientFactory()

        reactor.connectTCP(self.server, self.port, self.factory)

        d = defer.Deferred()

        def cb():
            # Wait until we have a useful proto object
            if hasattr(self.factory, 'proto') and self.factory.proto:
                d.callback(self.factory.proto)
            else:
                reactor.callLater(0.01, cb)

        cb()

        return d


    def setupSources(self, config):
        """Sets up source objects from the given config"""
        sources = config.get('sources', [])

        for source in sources:
            # Resolve the source
            cl = source['source'].split('.')[-1]                # class
            path = '.'.join(source['source'].split('.')[:-1])   # import path

            # Import the module and get the object source we care about
            sourceObj = getattr(importlib.import_module(path), cl)

            if not ('ttl' in source.keys()):
                source['ttl'] = self.ttl

            if not ('interval' in source.keys()):
                source['interval'] = self.inter

            self.sources.append(sourceObj(source, self.queueBack))

    def queueBack(self, event):
        """Callback that all event sources call when they have a new event
        or list of events
        """

        if isinstance(event, list):
            self.events.extend(event)
        else:
            self.events.append(event)

    def emptyEventQueue(self):
        if self.events:
            events = self.events
            self.events = []
            
            self.factory.proto.sendEvents(events)

    def tick(self):
        if self.factory.proto:
            # Check backpressure
            if (self.pressure < 0) or (self.proto.pressure <= self.pressure):
                self.emptyEventQueue()
        else:
            # Check queue age and expire stale events
            for i, e in enumerate(self.events):
                if e.time < (time.time() - e.ttl):
                    self.events.pop(i)

    @defer.inlineCallbacks
    def startService(self):
        yield self.connectClient()

        stagger = 0
        # Start sources internal timers
        for source in self.sources:
            # Stagger source timers, or use per-source start_delay
            start_delay = float(source.config.get('start_delay', stagger))
            reactor.callLater(start_delay, source.startTimer)
            stagger += self.stagger

        self.running = 1
        self.t.start(self.inter)
 
    def stopService(self):
        self.running = 0
        self.t.stop()

        if self.factory.proto:
            self.factory.stopTrying()
            self.factory.proto.transport.loseConnection()
