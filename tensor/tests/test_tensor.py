from twisted.trial import unittest

from twisted.internet import defer, reactor
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

from tensor.protocol import riemann

from tensor.objects import Event

class Tests(unittest.TestCase):
    def test_riemann_protobuf(self):
        proto = riemann.RiemannProtocol()

        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0)

        # Well, I guess we'll just assume this is right
        message = proto.encodeMessage([event])

    @defer.inlineCallbacks
    def test_riemann(self):

        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0)

        end = TCP4ClientEndpoint(reactor, "localhost", 5555)
       
        p = yield connectProtocol(end, riemann.RiemannProtocol())

        yield p.sendEvents([event])

        p.transport.loseConnection()

