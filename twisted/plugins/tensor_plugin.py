import yaml

from zope.interface import implements
 
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
 
import tensor
 
class Options(usage.Options):
    optParameters = [
        ["config", "c", "tensor.yml", "Config file"],
    ]
 
class TensorServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "tensor"
    description = "A Riemann(.io) event thingy"
    options = Options
 
    def makeService(self, options):
        config = yaml.load(open(options['config']))
        return tensor.makeService(config)
 
serviceMaker = TensorServiceMaker()

