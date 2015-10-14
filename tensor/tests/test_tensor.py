from twisted.trial import unittest

from twisted.internet import defer, reactor, error
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

from tensor.protocol import riemann

from tensor.objects import Event

from tensor.utils import fork

class Tests(unittest.TestCase):
    def setUp(self):
        self.endpoint = None

    def tearDown(self):
        if self.endpoint:
            return defer.maybeDeferred(self.endpoint.stopListening)

    def test_riemann_protobuf(self):
        proto = riemann.RiemannProtocol()

        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0)

        # Well, I guess we'll just assume this is right
        message = proto.encodeMessage([event])

    def test_riemann_protobuf_with_attributes(self):
        proto = riemann.RiemannProtocol()

        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      attributes={"chicken": "little"})

        e = proto.encodeEvent(event)
        attrs = e.attributes
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].key, "chicken")
        self.assertEqual(attrs[0].value, "little")

    @defer.inlineCallbacks
    def test_tcp_riemann(self):

        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0)

        end = TCP4ClientEndpoint(reactor, "localhost", 5555)
       
        p = yield connectProtocol(end, riemann.RiemannProtocol())

        yield p.sendEvents([event])

        p.transport.loseConnection()

    @defer.inlineCallbacks
    def test_udp_riemann(self):

        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0)
        
        protocol = riemann.RiemannUDP('127.0.0.1', 5555)
        self.endpoint = reactor.listenUDP(0, protocol)

        yield protocol.sendEvents([event])

    @defer.inlineCallbacks
    def test_utils_fork(self):
        o, e, c = yield fork('echo', args=('hi',))

        self.assertEquals(o, "hi\n")
        self.assertEquals(c, 0)

    @defer.inlineCallbacks
    def test_utils_fork_timeout(self):
        died = False
        try:
            o, e, c = yield fork('sleep', args=('2',), timeout=0.1)
        except error.ProcessTerminated:
            died = True

        self.assertTrue(died)
