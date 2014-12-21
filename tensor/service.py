import time
import os
import importlib
import re

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
        self.running = 0
        self.sources = []
        self.outputs = []

        self.evCache = {}
        self.critical = {}
        self.warn = {}

        self.eventCounter = 0

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
        self.debug = float(self.config.get('debug', False))
        self.ttl = float(self.config.get('ttl', 60.0))
        self.stagger = float(self.config.get('stagger', 0.2))

        # Backward compatibility
        self.server = self.config.get('server', 'localhost')
        self.port = int(self.config.get('port', 5555))
        self.proto = self.config.get('proto', 'tcp')
        self.inter = self.config.get('interval', 60.0)

        if self.debug:
            print "config:", repr(config)

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
            if not ('debug' in output):
                output['debug'] = self.debug

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

            if not ('debug' in source):
                source['debug'] = self.debug

            if not ('ttl' in source.keys()):
                source['ttl'] = self.ttl

            if not ('interval' in source.keys()):
                source['interval'] = self.inter

            for k, v in source.get('critical', {}).items():
                self.critical[re.compile(k)] = v
                
            for k, v in source.get('warning', {}).items():
                self.warn[re.compile(k)] = v

            self.sources.append(sourceObj(source, self.sendEvent, self))

    def _aggregateQueue(self, events):
        # Handle aggregation for each event
        queue = []
        for ev in events:
            if ev.aggregation:
                id = ev.id()
                if id in self.evCache:
                    tDelta = ev.time - self.evCache[id].time
                    m = ev.aggregation(
                        self.evCache[id].metric, ev.metric, tDelta)
                    queue.append(ev.copyWithMetric(m))

                self.evCache[id] = ev
            else:
                queue.append(ev)

        return queue

    def setStates(self, events):
        for ev in events:
            if ev.state == 'ok':
                for k, v in self.warn.items():
                    if k.match(ev.service):
                        s = eval("service %s" % v, {'service': ev.metric})
                        if s:
                            ev.state = 'warning'

                for k, v in self.critical.items():
                    if k.match(ev.service):
                        s = eval("service %s" % v, {'service': ev.metric})
                        if s:
                            ev.state = 'critical'

    def sendEvent(self, events):
        """Callback that all event sources call when they have a new event
        or list of events
        """

        if isinstance(events, list):
            self.eventCounter += len(events)
        else:
            self.eventCounter += 1
            events = [events]
    
        queue = self._aggregateQueue(events)
        self.setStates(queue)

        for output in self.outputs:
            if self.debug:
                log.msg("Sending events %s" % queue)
            reactor.callLater(0, output.eventsReceived, queue)

    @defer.inlineCallbacks
    def startService(self):
        yield self.setupOutputs(self.config)

        if self.debug:
            log.msg("Starting service")
        stagger = 0
        # Start sources internal timers
        for source in self.sources:
            if self.debug:
                log.msg("Starting source " + source.config['service'])
            # Stagger source timers, or use per-source start_delay
            start_delay = float(source.config.get('start_delay', stagger))
            reactor.callLater(start_delay, source.startTimer)
            stagger += self.stagger

        self.running = 1
 
    @defer.inlineCallbacks
    def stopService(self):
        self.running = 0

        for output in self.outputs:
            yield defer.maybeDeferred(output.stop)
