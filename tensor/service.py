import time
import socket

from twisted.application import service
from twisted.internet import task

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

class TensorService(service.Service):
    def __init__(self):
        self.t = task.LoopingCall(self.tick)
        self.running = 0
        self.inter = 1.0   # tick interval
 
    def tick(self):
        pass

    def startService(self):
        self.running = 1
        self.t.start(self.inter)
 
    def stopService(self):
        self.running = 0
        self.t.stop()
