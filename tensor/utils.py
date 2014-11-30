import signal
import time
from StringIO import StringIO

from twisted.internet import reactor, protocol, defer, error
from twisted.python import log
from twisted.names import client


class Resolver(object):
    def __init__(self):
        self.recs = {}
        
        self.resolver = client.getResolver()

    def reverseNameFromIPAddress(self, address):
        return '.'.join(reversed(address.split('.'))) + '.in-addr.arpa'

    def reverse(self, ip):
        def _ret(result, ip):
            host = ip
            if isinstance(result, tuple):
                answers, authority, additional = result
                if isinstance(answers, list):
                    ttl = answers[0].payload.ttl
                    host = answers[0].payload.name.name
                    self.recs[ip] = (host, ttl, time.time())

            return host

        if ip in self.recs:
            host, ttl, t = self.recs[ip]

            if (time.time() - t) < ttl:
                return defer.maybeDeferred(lambda x: x, host)

        return self.resolver.lookupPointer(
            name=self.reverseNameFromIPAddress(address=ip)
        ).addCallback(_ret, ip).addErrback(_ret, ip)

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
    """fork
    Provides a deferred wrapper function with a timeout function

    **Arguments:**

    :executable: Executable
    :type executable: str.

    **Keyword arguments:**

    :args: Tupple of arguments
    :type args: tupple.
    :env: Environment dictionary
    :type env: dict.
    :timeout: Kill the child process if timeout is exceeded
    :type timeout: int.
    """
    d = defer.Deferred()
    p = ProcessProtocol(d, timeout)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path)
    return d
