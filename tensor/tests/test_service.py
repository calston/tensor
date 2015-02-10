from twisted.trial import unittest

from twisted.internet import defer, reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import ServerFactory
from twisted.protocols.basic import Int32StringReceiver

from tensor.ihateprotobuf import proto_pb2
from tensor.objects import Event, Source, Output
from tensor.protocol.riemann import RiemannClientFactory
from tensor.service import TensorService
from tensor.aggregators import Counter32, Counter64, Counter


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


class FakeSource(Source):
    pass

class FakeOutput(Output):
    def __init__(self, *a):
        Output.__init__(self, *a)
        self.events = None

    def eventsReceived(self, events):
        self.events = events

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

    def make_source(self, service):
        source = FakeSource(
            {
                'service': 'test',
                'interval': 1.0,
                'ttl': 60.0
            },
            service.sendEvent, service)
        service.sources.append(source)
        return source

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

        source = self.make_source(service)
        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      hostname='localhost')
        service.sendEvent(source, event)
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
        source = self.make_source(service)
        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      hostname='localhost')
        service.sendEvent(source, event)
        [msg] = yield factory.wait_for_messages(1)
        [event] = msg.events
        self.assertEqual(event.description, 'Sky has not fallen')

        # Disconnect and hope we reconnect
        [output] = service.outputs[None]
        yield output.connector.disconnect()
        yield wait(0.2)

        # Send another event to make sure everything's still happy
        [_] = yield factory.wait_for_messages(1)
        event = Event('ok', 'sky', 'Sky has not fallen', 1.0, 60.0,
                      hostname='localhost')
        service.sendEvent(source, event)
        [_, msg2] = yield factory.wait_for_messages(2)
        [event] = msg.events
        self.assertEqual(event.description, 'Sky has not fallen')

    def _aggregator_test(self, m1, m2, aggregator, delta):
        service = self.make_service({})

        ev1 = Event('ok', 'num', 'Number', m1, delta, 
            hostname='localhost', aggregation=aggregator)

        ev2 = Event('ok', 'num', 'Number', m2, delta, 
            hostname='localhost', aggregation=aggregator)

        ev1.time = 1
        ev2.time = delta+1

        q1 = service._aggregateQueue([ev1])
        ev = service._aggregateQueue([ev2])[0]

        self.assertEqual(q1, [])

        return ev.metric

    def test_aggregate_counter32(self):
        metric = self._aggregator_test(1, 2, Counter32, 4)
        self.assertEqual(metric, 0.25)

    def test_aggregate_counter64(self):
        metric = self._aggregator_test(1, 2, Counter64, 4)
        self.assertEqual(metric, 0.25)

    def test_aggregate_counter(self):
        metric = self._aggregator_test(1, 2, Counter, 4)
        self.assertEqual(metric, 0.25)

    def test_aggregate_counter32_rollover(self):
        metric = self._aggregator_test(4294967290, 5, Counter32, 4)
        self.assertEqual(metric, 2.5)
 
    def test_aggregate_counter64_rollover(self):
        metric = self._aggregator_test(18446744073709551610, 5, Counter64, 4)
        self.assertEqual(metric, 2.5)

    def test_state_match(self):
        service = self.make_service({
            'interval': 1.0, 'ttl': 60.0, 
            'sources': [{
                'source': 'tensor.sources.linux.basic.Network', 
                'interval': 2.0, 
                'critical': {'network.\\w+.tx_bytes': '> 500'}, 
                'warning': {'network.\\w+.tx_bytes': '> 100'}, 
                'service': 'network'}]
        })

        ev1 = Event('ok', 'network.foo.tx_bytes', 'net1', 50, 1,
            hostname='localhost')
        ev2 = Event('ok', 'network.foo.tx_bytes', 'net1', 1000, 1,
            hostname='localhost')
        ev3 = Event('ok', 'network.foo.tx_bytes', 'net1', 200, 1,
            hostname='localhost')
        
        service.setStates(service.sources[0], [ev1, ev2, ev3])

        self.assertEqual(ev1.state, 'ok')
        self.assertEqual(ev2.state, 'critical')
        self.assertEqual(ev3.state, 'warning')

    @defer.inlineCallbacks
    def test_source_routing(self):
        service = self.make_service({
            'interval': 1.0, 'ttl': 60.0, 
            'sources': [{
                'source': 'tensor.sources.linux.basic.LoadAverage', 
                'interval': 2.0,
                'route': 'out1',
                'service': 'load'}]
        })

        output1 = FakeOutput({}, service)
        output2 = FakeOutput({}, service)

        [source] = service.sources

        service.outputs = {
            'out1':[output1],
            'out2':[output2]
        }

        event = Event('ok', 'load', 'load', 1, 1, hostname='localhost')

        service.sendEvent(source, event)

        yield wait(0.2)

        self.assertEqual(len(output1.events), 1)
        self.assertEqual(output2.events, None)
       
        output1.events = None
        source.config['route'] = ['out1', 'out2']

        service.sendEvent(source, event)

        yield wait(0.2)

        self.assertEqual(len(output1.events), 1)
        self.assertEqual(len(output2.events), 1)
