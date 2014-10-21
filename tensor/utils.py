import signal
from StringIO import StringIO

from twisted.internet import reactor, protocol, defer, error
from twisted.python import log


class BodyReceiver(protocol.Protocol):
    """ Simple buffering consumer for body objects """
    def __init__(self, finished):
        self.finished = finished
        self.buffer = StringIO()

    def dataReceived(self, buffer):
        self.buffer.write(buffer)

    def connectionLost(self, reason):
        self.buffer.seek(0)
        self.finished.callback(self.buffer)

class ProcessProtocol(protocol.ProcessProtocol):
    """ProcessProtocol which supports timeouts"""
    def __init__(self, deferred, timeout):
        self.timeout = timeout
        self.timer = None

        self.deferred = deferred
        self.outBuf = StringIO()
        self.errBuf = StringIO()
        self.outReceived = self.outBuf.write
        self.errReceived = self.errBuf.write

    def processEnded(self, reason):
        if self.timer and (not self.timer.called):
            self.timer.cancel()

        out = self.outBuf.getvalue()
        err = self.errBuf.getvalue()

        e = reason.value
        code = e.exitCode

        if e.signal:
            self.deferred.errback(reason)
        else:
            self.deferred.callback((out, err, code))

    def connectionMade(self):
        @defer.inlineCallbacks
        def killIfAlive():
            log.msg('Killing source proccess: Timeout %s exceeded' % self.timeout)
            yield self.transport.signalProcess('KILL')

        self.timer = reactor.callLater(self.timeout, killIfAlive)

def fork(executable, args=(), env={}, path=None, timeout=3600):
    d = defer.Deferred()
    p = ProcessProtocol(d, timeout)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path)
    return d
