from tensor.ihateprotobuf import proto_pb2
from tensor.protocol.interface import ITensorProtocol

from zope.interface import implements

from twisted.protocols.basic import Int32StringReceiver


class RiemannProtocol(Int32StringReceiver):
    implements(ITensorProtocol)

    def sendEvent(event):
        pbevent = proto_pb2.Event(
            time=event.time,
            state=event.state,
            service=event.service,
            host=self.hostname,
            description=event.description,
            tags=event.tags,
            ttl=60.0,
            metric_=event.metric # Huh? Where?
        )


    def sendMessage():
        pass

