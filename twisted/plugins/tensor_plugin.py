from zope.interface import implements
 
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
 
import tensor
 
class Options(usage.Options):
    optParameters = []
 
class TensorServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "tensor"
    description = "A Riemann(.io) event thingy"
    options = Options
 
    def makeService(self, options):
        return tensor.makeService()
 
serviceMaker = TensorServiceMaker()

