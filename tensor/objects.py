import time
import socket
import exceptions

from twisted.internet import task, defer

class Event(object):
    def __init__(self, state, service, description, metric, tags=[]):
        """Construct an Event object

        Arguments:
        state -- Some sort of string < 255 chars describing the state
        service -- The service name for this event
        description -- A description for the event, ie. "My house is on fire!"
        metric -- int or float metric for this event

        Keyword arguments:
        tags -- List of tag strings"""

        self.state = state
        self.service = service
        self.description = description
        self.tags = tags
        self.metric = metric

        self.time = time.time()
        self.hostname = socket.gethostbyaddr(socket.gethostname())[0]

class Source(object):
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

        self.queueBack = queueBack

    def startTimer(self):
        """Starts the timer for this source"""
        self.t.start(self.inter)

    @defer.inlineCallbacks
    def tick(self):
        """Called for every timer tick. Calls self.get which can be a deferred
        and passes that result back to the queueBack method"""
        event = yield defer.maybeDeferred(self.get)

        self.queueBack(event)

    def get(self):
        raise exceptions.NotImplementedError
