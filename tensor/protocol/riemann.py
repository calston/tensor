from tensor.ihateprotobuf import proto_pb2
from tensor.interfaces import ITensorProtocol

from zope.interface import implements

from twisted.protocols.basic import Int32StringReceiver
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import protocol
from twisted.python import log

class RiemannProtobufMixin(object):
    def encodeEvent(self, event):
        """Adapts an Event object to a Riemann protobuf event Event"""
        pbevent = proto_pb2.Event(
            time=int(event.time),
            state=event.state,
            service=event.service,
            host=event.hostname,
            description=event.description,
            tags=event.tags,
            ttl=event.ttl,
        )

        if event.metric is not None:
            # I have no idea what I'm doing
            if isinstance(event.metric, int):
                pbevent.metric_sint64 = event.metric
                pbevent.metric_f = float(event.metric)
            else:
                pbevent.metric_d = float(event.metric)
                pbevent.metric_f = float(event.metric)
        if event.attributes is not None:
            for key, value in event.attributes.items():
                attribute = pbevent.attributes.add()
                attribute.key, attribute.value = key, value

        return pbevent

    def encodeMessage(self, events):
        """Encode a list of Tensor events with protobuf"""

        message = proto_pb2.Msg(
            events=[self.encodeEvent(e) for e in events if e._type=='riemann']
        )

        return message.SerializeToString()

    def decodeMessage(self, data):
        """Decode a protobuf message into a list of Tensor events"""
        message = proto_pb2.Msg()
        message.ParseFromString(data)

        return message
    
    def sendEvents(self, events):
        """Send a Tensor Event to Riemann"""
        self.pressure += 1
        self.sendString(self.encodeMessage(events))

class RiemannProtocol(Int32StringReceiver, RiemannProtobufMixin):
    """Riemann protobuf protocol
    """
    implements(ITensorProtocol)

    def __init__(self):
        self.pressure = 0

    def stringReceived(self, string):
        self.pressure -= 1

class RiemannClientFactory(protocol.ReconnectingClientFactory):
    """A reconnecting client factory which creates RiemannProtocol instances
    """
    maxDelay = 30
    initialDelay = 5
    factor = 2
    jitter = 0

    def __init__(self, hosts, failover=False):
        self.failover = failover

        if self.failover:
            if isinstance(hosts, list):
                self.hosts = hosts
            else:
                self.hosts = [hosts]

        self.host_index = 0

    def buildProtocol(self, addr):
        self.resetDelay()
        self.proto = RiemannProtocol()
        return self.proto

    def _do_failover(self, connector):
        if self.failover:
            if self.host_index >= (len(self.hosts)-1):
                self.host_index = 0
            else:
                self.host_index += 1

            connector.host = self.hosts[self.host_index]

    def clientConnectionLost(self, connector, reason):
        log.msg('Lost connection.  Reason:' + str(reason))
        self.proto = None

        self._do_failover(connector)

        log.msg('Reconnecting to Riemann on %s:%s' % (connector.host, connector.port))
        protocol.ReconnectingClientFactory.clientConnectionLost(
            self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.msg('Connection failed. Reason:' + str(reason))
        self.proto = None

        self._do_failover(connector)

        log.msg('Reconnecting to Riemann on %s:%s' % (connector.host, connector.port))
        protocol.ReconnectingClientFactory.clientConnectionFailed(
            self, connector, reason)

class RiemannUDP(DatagramProtocol, RiemannProtobufMixin):
    """UDP datagram protocol for Riemann
    """
    implements(ITensorProtocol)

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.pressure = 0

    def sendString(self, string):
        self.transport.write(string, (self.host, self.port))
        self.pressure -= 1
