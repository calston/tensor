import time
import sys
import os
import importlib
import re
import copy

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
        self.lastEvents = {}
        self.outputs = {}

        self.evCache = {}
        self.critical = {}
        self.warn = {}

        self.eventCounter = 0

        self.factory = None
        self.protocol = None
        self.watchdog = None

        self.config = config

        both = lambda i1, i2, t: isinstance(i1, t) and isinstance(i2, t)

        if os.path.exists('/var/lib/tensor'):
            sys.path.append('/var/lib/tensor')

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

            # Import the module and construct the output object
            outputObj = getattr(
                importlib.import_module(path), cl)(output, self)

            name = output.get('name', None)

            # Add the output to our routing hash
            if name in self.outputs:
                self.outputs[name].append(outputObj)
            else:
                self.outputs[name] = [outputObj]

            # connect the output
            reactor.callLater(0, outputObj.createClient)

    def createSource(self, source):
        # 
        if source.get('path'):
            path = source['path']
            if path not in sys.path:
                sys.path.append(path)

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

        return sourceObj(source, self.sendEvent, self)

    def setupTriggers(self, source, sobj):
        if source.get('critical'):
            self.critical[sobj] = [
                (re.compile(k), v) for k, v in source['critical'].items()
            ]

        if source.get('warning'):
            self.warn[sobj] = [
                (re.compile(k), v) for k, v in source['warning'].items()
            ]

    def setupSources(self, config):
        """Sets up source objects from the given config"""
        sources = config.get('sources', [])

        for source in sources:
            src = self.createSource(source)
            self.setupTriggers(source, src)

            self.sources.append(src)

    def _aggregateQueue(self, events):
        # Handle aggregation for each event
        queue = []
        for ev in events:
            if ev.aggregation:
                id = ev.id()
                thisM = ev.metric

                if id in self.evCache:
                    lastM, lastTime = self.evCache[id]
                    tDelta = ev.time - lastTime
                    m = ev.aggregation(
                        lastM, ev.metric, tDelta)
                    if m:
                        ev.metric = m
                        queue.append(ev)

                self.evCache[id] = (thisM, ev.time)
            else:
                queue.append(ev)

        return queue

    def setStates(self, source, queue):
        for ev in queue:
            if ev.state == 'ok':
                for k, v in self.warn.get(source, []):
                    if k.match(ev.service):
                        s = eval("service %s" % v, {'service': ev.metric})
                        if s:
                            ev.state = 'warning'

                for k, v in self.critical.get(source, []):
                    if k.match(ev.service):
                        s = eval("service %s" % v, {'service': ev.metric})
                        if s:
                            ev.state = 'critical'

    def routeEvent(self, source, events):
        routes = source.config.get('route', None)
    
        if not isinstance(routes, list):
            routes = [routes]

        for route in routes:
            if self.debug:
                log.msg("Sending events %s to %s" % (events, route))
 
            if not route in self.outputs:
                # Non existant route
                log.msg('Could not route %s -> %s.' % (
                    source.config['service'], route))
            else:
                for output in self.outputs[route]:
                   reactor.callLater(0, output.eventsReceived, events)

    def sendEvent(self, source, events):
        """Callback that all event sources call when they have a new event
        or list of events
        """

        if isinstance(events, list):
            self.eventCounter += len(events)
        else:
            self.eventCounter += 1
            events = [events]
    
        queue = self._aggregateQueue(events)

        if queue:
            if (source in self.critical) or (source in self.warn):
                self.setStates(source, queue)

            self.routeEvent(source, queue)

        queue = []

        self.lastEvents[source] = time.time()

    def _startSource(self, source):
        source.startTimer()

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
            reactor.callLater(start_delay, self._startSource, source)
            stagger += self.stagger

        reactor.callLater(stagger, self.startWatchdog)
        self.running = 1
 
    def startWatchdog(self):
        # Start source watchdog
        self.watchdog = task.LoopingCall(self.sourceWatchdog)
        self.watchdog.start(10)

    def sourceWatchdog(self):
        """Watchdog timer function. 

        Recreates sources which have not generated events in 10*interval if
        they have watchdog set to true in their configuration
        """
        for i, source in enumerate(self.sources):
            if not source.config.get('watchdog', False):
                continue 
            sn = repr(source)
            last = self.lastEvents.get(source, None)
            if last:
                try:
                    if last < (time.time()-(source.inter*10)):
                        log.msg("Trying to restart stale source %s: %ss" % (
                            sn, int(time.time() - last)
                        ))

                        s = self.sources.pop(i)
                        try:
                            s.t.stop()
                        except Exception, e:
                            log.msg("Could not stop timer for %s: %s" % (
                                sn, e))

                        config = copy.deepcopy(s.config)

                        del self.lastEvents[source]
                        del s, source

                        source = self.createSource(config)

                        reactor.callLater(0, self._startSource, source)
                except Exception, e:
                    log.msg("Could not reset source %s: %s" % (
                        sn, e))

    @defer.inlineCallbacks
    def stopService(self):
        self.running = 0

        if self.watchdog:
            self.watchdog.stop()

        for n, outputs in self.outputs.items():
            for output in outputs:
                yield defer.maybeDeferred(output.stop)
