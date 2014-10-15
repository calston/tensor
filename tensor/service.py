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
        self.inter = 1.0   # tick interval
        self.sources = []

        self.setupSources(config)

    def setupSources(self, config):
        sources = config.get('sources', [])

        for source in sources:
            # Resolve the source
            cl = source['source'].split('.')[-1]                # class
            path = '.'.join(source['source'].split('.')[:-1])   # import path

            # Import the module and get the object source we care about
            sourceObj = getattr(importlib.import_module(path), cl)

            self.sources.append(sourceObj(source, self.queueBack))

    @defer.inlineCallbacks
    def queueBack(self, event):
        """Callback that all event sources call when they have a new event"""

        # Shity way of doing things, but tempermenant
        end = TCP4ClientEndpoint(reactor, "localhost", 5555)

        p = yield connectProtocol(end, riemann.RiemannProtocol())

        yield p.sendEvents([event])

        p.transport.loseConnection()
 

    def tick(self):
        pass

    def startService(self):
        self.running = 1
        self.t.start(self.inter)

        for source in self.sources:
            source.startTimer()
 
    def stopService(self):
        self.running = 0
        self.t.stop()
