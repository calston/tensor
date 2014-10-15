from zope.interface import Interface


class ITensorProtocol(Interface):
    """
    Interface for Tensor client protocols
    """

    def sendEvent(self, event):
        """Sends an event to this client"""
        pass

