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
        self.queues = self.tensor.queueCounter

        self.rtime = time.time()

    def get(self):
        events = []

        sources = len(self.tensor.sources)
        events = len(self.tensor.events)

        t_delta = time.time() - self.rtime

        qrate = (self.tensor.queueCounter - self.queues)/t_delta
        erate = (self.tensor.eventCounter - self.events)/t_delta

        self.queues = self.tensor.queueCounter
        self.events = self.tensor.eventCounter

        self.rtime = time.time()
        
        return [
            self.createEvent('ok', 'De-queue rate', qrate,
                prefix="dequeue rate"),
            self.createEvent('ok', 'Event queue rate', erate,
                prefix="event qrate"),
            self.createEvent('ok', 'Event queue size', events,
                prefix="event qsize"),
            self.createEvent('ok', 'Sources', sources, prefix="sources"),
        ]
