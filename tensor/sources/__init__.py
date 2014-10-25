import time

from zope.interface import implements

from twisted.internet import defer

from tensor.interfaces import ITensorSource
from tensor.objects import Source

class Tensor(Source):
    """Reports Tensor information about numbers of checks
    and queue sizes.

    **Metrics:**

    :(service name).event qrate: Events added to the queue per second
    :(service name).dequeue rate: Events removed from the queue per second
    :(service name).event qsize: Number of events held in the queue
    :(service name).sources: Number of sources running
    """
    implements(ITensorSource)

    def __init__(self, *a):
        Source.__init__(self, *a)

        self.events = self.tensor.eventCounter
        self.rtime = time.time()

    def get(self):
        events = []

        sources = len(self.tensor.sources)

        t_delta = time.time() - self.rtime

        erate = (self.tensor.eventCounter - self.events)/t_delta

        self.events = self.tensor.eventCounter

        self.rtime = time.time()
        
        return [
            self.createEvent('ok', 'Event rate', erate, prefix="event rate"),
            self.createEvent('ok', 'Sources', sources, prefix="sources"),
        ]
