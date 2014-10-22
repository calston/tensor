import time
import socket
import exceptions

from twisted.internet import task, defer

class Event(object):
    """Tensor Event object

    All sources pass these to the queue, which form a proxy object
    to create protobuf Event objects

    **Arguments:**

    :state: Some sort of string < 255 chars describing the state
    :service: The service name for this event
    :description: A description for the event, ie. "My house is on fire!"
    :metric: int or float metric for this event

    **Keyword arguments:**

    :tags: List of tag strings
    :hostname: Hostname for the event (defaults to system fqdn)
    """
    def __init__(self, state, service, description, metric, ttl, tags=[], hostname=None):
        self.state = state
        self.service = service
        self.description = description
        self.metric = metric
        self.ttl = ttl
        self.tags = tags

        self.time = time.time()
        if hostname:
            self.hostname = hostname
        else:
            self.hostname = socket.gethostbyaddr(socket.gethostname())[0]

class Source(object):
    """Source parent class

    Sources can inherit this object which provides a number of
    utility methods.

    **Arguments:**

    :config: Dictionary config for this queue (usually read from the
             yaml configuration)
    :queueBack: A callback method to recieve a list of Event objects
    """

    def __init__(self, config, queueBack):
        """Consturct a Source object

        Arguments:
        config -- Dictionary config for this source
        queueBack -- Callback method for events originating from this source
                     called on config['interval']
        """
        self.config = config
        self.t = task.LoopingCall(self.tick)

        self.service = config['service']
        self.inter = float(config['interval'])
        self.ttl = float(config['ttl'])

        self.hostname = config.get('hostname',
            socket.gethostbyaddr(socket.gethostname())[0])

        self.queueBack = queueBack

    def startTimer(self):
        """Starts the timer for this source"""
        self.t.start(self.inter)

    @defer.inlineCallbacks
    def tick(self):
        """Called for every timer tick. Calls self.get which can be a deferred
        and passes that result back to the queueBack method
        
        Returns a deferred"""
        event = yield defer.maybeDeferred(self.get)

        if event:
            self.queueBack(event)

    def createEvent(self, state, description, metric, prefix=None):
        """Creates an Event object from the Source configuration"""
        if prefix:
            service_name = self.service + "." + prefix
        else:
            service_name = self.service

        # Dynamic state check (unless the check already set it)
        if state == "ok":
            critical = self.config.get('critical', {}).get(service_name, None)
            warn = self.config.get('warning', {}).get(service_name, None)

            if warn:
                s = eval("service %s" % warn, {'service': metric})
                if s:
                    state = 'warning'

            if critical:
                s = eval("service %s" % critical, {'service': metric})
                if s:
                    state = 'critical'

        return Event(state, service_name, description, metric, self.ttl,
            hostname = self.hostname
        )

    def get(self):
        raise exceptions.NotImplementedError()
