from tensor.ihateprotobuf import proto_pb2
from tensor.protocol.interface import ITensorProtocol

from zope.interface import implements

from twisted.protocols.basic import Int32StringReceiver


class RiemannProtocol(Int32StringReceiver):
    implements(ITensorProtocol)

    def encodeMessage(self, event):
        """Encode a Tensor event object in some rebranded archaic serialisatin
        format called protobuf"""

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

        # Should probably pool and merge events somewhere
        message = proto_pb2.Msg(events=[pbevent])

        return message.SerializeToString()

    def sendEvent(self, event):
        self.sendString(self.encodeMessage(event))

