from twisted.trial import unittest

from twisted.internet import defer, reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import ServerFactory
from twisted.protocols.basic import Int32StringReceiver

from tensor.ihateprotobuf import proto_pb2
from tensor.objects import Event
from tensor.protocol.riemann import RiemannClientFactory
from tensor.service import TensorService


def wait(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d


class FakeRiemannServerProtocol(Int32StringReceiver):
    def stringReceived(self, string):
        msg = proto_pb2.Msg.FromString(string)
        self.factory.receive_message(msg)
        self.sendString(proto_pb2.Msg(ok=True).SerializeToString())


class FakeRiemannServerFactory(ServerFactory):
    protocol = FakeRiemannServerProtocol
    endpoint = None
    listener = None

    def __init__(self):
        self.received_messages = []
        self.waiters = []

    def start_listening(self, endpoint):
        def cb(listener):
            self.listener = listener
            return self

        self.endpoint = endpoint
        return endpoint.listen(self).addCallback(cb)

    def stop_listening(self):
        if self.listener is not None:
            return self.listener.stopListening()

    def reconnect(self):
        return self.listener.startListening()

    def get_host(self):
        if self.listener is not None:
            return self.listener.getHost()

    def receive_message(self, msg):
        self.received_messages.append(msg)
        self._process_waiters()

    def _process_waiters(self):
        new_waiters = []
        firing_waiters = []
        while self.waiters:
            d, total_messages = self.waiters.pop(0)
            if len(self.received_messages) >= total_messages:
                firing_waiters.append(d)
            else:
                new_waiters.append((d, total_messages))
        self.waiters = new_waiters
        for d in firing_waiters:
            d.callback(self.received_messages[:])

    def wait_for_messages(self, total_messages):
        d = defer.Deferred()
        self.waiters.append((d, total_messages))
        self._process_waiters()
        return d


class TestService(unittest.TestCase):
    timeout = 10

    def start_riemann_server(self):
        factory = FakeRiemannServerFactory()
        self.addCleanup(factory.stop_listening)
        return factory.start_listening(TCP4ServerEndpoint(reactor, 0))

    def make_service(self, config):
        service = TensorService(config)
        self.addCleanup(self.stop_service, service)
        return service

    @defer.inlineCallbacks
    def stop_service(self, service):
        """
        Wait a little bit before and after stopping the service for things to
        happen in the right order. :-(
        """
        yield wait(0.1)
        yield service.stopService()
        yield wait(0.1)

    @defer.inlineCallbacks
    def test_service_sends_event(self):
        factory = yield self.start_riemann_server()
        service = self.make_service({"port": factory.get_host().port})
        yield service.startService()

        [] = yield factory.wait_for_messages(0)
        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      hostname='localhost')
        service.sendEvent(event)
        [msg] = yield factory.wait_for_messages(1)
        [event] = msg.events
        self.assertEqual(event.description, 'Sky has not fallen')

    @defer.inlineCallbacks
    def test_service_sends_event_after_reconnect(self):
        self.patch(RiemannClientFactory, 'initialDelay', 0.1)
        factory = yield self.start_riemann_server()
        service = self.make_service({"port": factory.get_host().port})
        yield service.startService()

        # Send an event to make sure everything's happy
        [] = yield factory.wait_for_messages(0)
        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      hostname='localhost')
        service.sendEvent(event)
        [msg] = yield factory.wait_for_messages(1)
        [event] = msg.events
        self.assertEqual(event.description, 'Sky has not fallen')

        # Disconnect and hope we reconnect
        [output] = service.outputs
        yield output.connector.disconnect()
        yield wait(0.2)

        # Send another event to make sure everything's still happy
        [_] = yield factory.wait_for_messages(1)
        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      hostname='localhost')
        service.sendEvent(event)
        [_, msg2] = yield factory.wait_for_messages(2)
        [event] = msg.events
        self.assertEqual(event.description, 'Sky has not fallen')
