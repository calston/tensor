import yaml

from zope.interface import implementer
 
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
 
import tensor


class Options(usage.Options):
    optParameters = [
        ["config", "c", "tensor.yml", "Config file"],
    ]
 

@implementer(IServiceMaker, IPlugin)
class TensorServiceMaker(object):
    tapname = "tensor"
    description = "A Riemann(.io) event thingy"
    options = Options
 
    def makeService(self, options):
        config = yaml.load(open(options['config']))
        return tensor.makeService(config)
 
serviceMaker = TensorServiceMaker()
