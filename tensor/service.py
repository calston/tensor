import time
import os
import importlib

import yaml

from twisted.application import service
from twisted.internet import task, reactor, defer
from twisted.python import log

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
        self.outputs = []

        self.eventCounter = 0
        self.queueCounter = 0
        self.queueExpire = 0

        self.factory = None
        self.protocol = None

        self.config = config

        both = lambda i1, i2, t: isinstance(i1, t) and isinstance(i2, t)

        if 'include_path' in config:
            ipath = config['include_path']
            if os.path.exists(ipath):
                files = [
                    os.path.join(ipath, f) for f in os.listdir(ipath)
                        if f[-4:] == '.yml'
                ]

                for f in files:
                    conf = yaml.load(open(f, 'rt'))
                    for k,v in conf.items():
                        if k in self.config:
                            if both(v, self.config[k], dict):
                                # Merge dicts
                                for k2, v2 in v.items():
                                    self.config[k][j2] = v2

                            elif both(v, self.config[k], list):
                                # Extend lists
                                self.config[k].extend(v)
                            else:
                                # Overwrite
                                self.config[k] = v
                        else:
                            self.config[k] = v
                    log.msg('Loadded additional configuration from %s' % f)
            else:
                log.msg('Config Error: include_path %s does not exist' % ipath)

        # Read some config stuff
        self.inter = float(self.config['interval'])  # tick interval
        self.server = self.config.get('server', 'localhost')
        self.port = int(self.config.get('port', 5555))
        self.pressure = int(self.config.get('pressure', -1))
        self.ttl = float(self.config.get('ttl', 60.0))
        self.stagger = float(self.config.get('stagger', 0.2))


        self.proto = self.config.get('proto', 'tcp')

        self.setupSources(self.config)

    def setupOutputs(self, config):
        """Setup output processors"""

        if self.proto == 'tcp':
            defaultOutput = {
                'output': 'tensor.outputs.riemann.RiemannTCP',
                'server': self.server,
                'port': self.port
            }
        else:
            defaultOutput = {
                'output': 'tensor.outputs.riemann.RiemannUDP',
                'server': self.server,
                'port': self.port
            }

        outputs = config.get('outputs', [defaultOutput])

        for output in outputs:
            cl = output['output'].split('.')[-1]                # class
            path = '.'.join(output['output'].split('.')[:-1])   # import path

            # Import the module and get the object output we care about
            outputObj = getattr(importlib.import_module(path), cl)

            self.outputs.append(outputObj(output, self))

        for output in self.outputs:
            # connect the output
            reactor.callLater(0, output.createClient)

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

            self.sources.append(sourceObj(source, self.queueBack, self))

    def queueBack(self, event):
        """Callback that all event sources call when they have a new event
        or list of events
        """

        if isinstance(event, list):
            self.events.extend(event)
            self.queueCounter += len(event)
        else:
            self.events.append(event)
            self.queueCounter += 1

    def emptyEventQueue(self):
        if self.events:
            events = self.events
            self.eventCounter += len(events)
            self.events = []

            for output in self.outputs:
                reactor.callLater(0, output.eventsReceived, events)

    def tick(self):
        # Check queue age and expire stale events
        for i, e in enumerate(self.events):
            if e.time < (time.time() - e.ttl):
                self.events.pop(i)
                self.queueExpire += 1

        self.emptyEventQueue()

    @defer.inlineCallbacks
    def startService(self):
        yield self.setupOutputs(self.config)

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

        if self.protocol:
            if self.factory:
                self.factory.stopTrying()
                self.protocol.transport.loseConnection()
            else:
                self.endpoint.stopListening()
