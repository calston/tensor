from twisted.application import service
from twisted.internet import task


class TensorService(service.Service):
    def __init__(self):
        self.t = task.LoopingCall(self.tick)
        self.running = 0
        self.inter = 1.0   # tick interval
 
    def tick(self):
        pass

    def startService(self):
        self.running = 1
        self.t.start(self.inter)
 
    def stopService(self):
        self.running = 0
        self.t.stop()
