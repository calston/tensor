from tensor.ihateprotobuf import proto_pb2
from tensor.interfaces import ITensorProtocol

from zope.interface import implements

from twisted.protocols.basic import Int32StringReceiver


class RiemannProtocol(Int32StringReceiver):
    implements(ITensorProtocol)

    def encodeEvent(self, event):
        pbevent = proto_pb2.Event(
            time=int(event.time),
            state=event.state,
            service=event.service,
            host=event.hostname,
            description=event.description,
            tags=event.tags,
            ttl=60.0,
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
        self.sendString(self.encodeMessage(events))

