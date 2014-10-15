import time
import importlib

from twisted.application import service
from twisted.internet import task, reactor, defer

from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

from tensor.protocol import riemann


class TensorService(service.Service):
    def __init__(self, config):
        self.t = task.LoopingCall(self.tick)
        self.running = 0
        self.inter = float(config['interval'])  # tick interval
        self.sources = []

        self.events = []

        self.setupSources(config)

    def setupSources(self, config):
        """Sets up source objects from the given config"""
        sources = config.get('sources', [])

        for source in sources:
            # Resolve the source
            cl = source['source'].split('.')[-1]                # class
            path = '.'.join(source['source'].split('.')[:-1])   # import path

            # Import the module and get the object source we care about
            sourceObj = getattr(importlib.import_module(path), cl)

            self.sources.append(sourceObj(source, self.queueBack))

    def queueBack(self, event):
        """Callback that all event sources call when they have a new event"""

        self.events.append(event)

    def emptyEventQueue(self):
        if self.events:
            events = self.events
            self.events = []
            
            self.proto.sendEvents(events)

    def tick(self):
        reactor.callLater(0.1, self.emptyEventQueue)

    @defer.inlineCallbacks
    def startService(self):
        self.running = 1
        self.t.start(self.inter)

        # TODO: Make this a reconnecting client factory
        endpoint = TCP4ClientEndpoint(reactor, "localhost", 5555)

        self.proto = yield connectProtocol(endpoint, riemann.RiemannProtocol())

        # Start sources internal timers
        for source in self.sources:
            source.startTimer()
 
    def stopService(self):
        self.running = 0
        self.t.stop()

        self.proto.transport.loseConnection()
