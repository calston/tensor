from tensor.ihateprotobuf import proto_pb2
from tensor.interfaces import ITensorProtocol

from zope.interface import implements

from twisted.protocols.basic import Int32StringReceiver
from twisted.internet import protocol
from twisted.python import log


class RiemannProtocol(Int32StringReceiver):
    """Riemann protobuf protocol
    """
    implements(ITensorProtocol)

    def __init__(self):
        self.pressure = 0

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

        # I have no idea what I'm doing
        if isinstance(event.metric, int):
            pbevent.metric_sint64 = event.metric
            pbevent.metric_f = float(event.metric)
        else:
            pbevent.metric_d = float(event.metric)
            pbevent.metric_f = float(event.metric)

        return pbevent

    def encodeMessage(self, events):
        """Encode a list of Tensor events with protobuf"""

        message = proto_pb2.Msg(
            events=[self.encodeEvent(e) for e in events]
        )

        return message.SerializeToString()
    
    def sendEvents(self, events):
        """Send a Tensor Event to Riemann"""
        self.pressure += 1
        self.sendString(self.encodeMessage(events))

    def stringReceived(self, string):
        self.pressure -= 1

class RiemannClientFactory(protocol.ReconnectingClientFactory):
    """A reconnecting client factory which creates RiemannProtocol instances
    """
    def buildProtocol(self, addr):
        self.resetDelay()
        self.proto = RiemannProtocol()
        return self.proto

    def clientConnectionLost(self, connector, reason):
        log.msg('Lost connection.  Reason:' + str(reason))
        self.proto = None
        protocol.ReconnectingClientFactory.clientConnectionLost(
            self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.msg('Connection failed. Reason:' + str(reason))
        self.proto = None
        protocol.ReconnectingClientFactory.clientConnectionFailed(
            self, connector, reason)

