import signal
import json
import time
import urllib
from StringIO import StringIO

from zope.interface import implements

from twisted.internet import reactor, protocol, defer, error
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent
from twisted.names import client
from twisted.python import log

class Timeout(Exception):
    """
    Raised to notify that an operation exceeded its timeout.
    """

class Resolver(object):
    """Helper class for DNS resolution
    """

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

class StringProducer(object):
    """String producer for writing to HTTP requests
    """
    implements(IBodyProducer)
 
    def __init__(self, body):
        self.body = body
        self.length = len(body)
 
    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)
 
    def pauseProducing(self):
        pass
 
    def stopProducing(self):
        pass

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
            try:
                yield self.transport.signalProcess('KILL')
                log.msg('Killed source proccess: Timeout %s exceeded' % self.timeout)
            except error.ProcessExitedAlready:
                pass

        self.timer = reactor.callLater(self.timeout, killIfAlive)

def fork(executable, args=(), env={}, path=None, timeout=3600):
    """fork
    Provides a deferred wrapper function with a timeout function

    :param executable: Executable
    :type executable: str.
    :param args: Tupple of arguments
    :type args: tupple.
    :param env: Environment dictionary
    :type env: dict.
    :param timeout: Kill the child process if timeout is exceeded
    :type timeout: int.
    """
    d = defer.Deferred()
    p = ProcessProtocol(d, timeout)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path)
    return d


class HTTPRequest(object):
    def __init__(self, timeout=120):
        self.timeout = timeout

    def abort_request(self, agent):
        """Called to abort request on timeout"""
        self.timedout = True
        if not agent.called:
            try:
                agent.cancel()
            except error.AlreadyCancelled:
                return
        
    @defer.inlineCallbacks
    def response(self, request):
        if request.length:
            d = defer.Deferred()
            request.deliverBody(BodyReceiver(d))
            b = yield d
            body = b.read()
        else:
            body = ""

        defer.returnValue(body)

    def request(self, url, method='GET', headers={}, data=None):
        self.timedout = False
        agent = Agent(reactor).request(method, url,
            Headers(headers),
            StringProducer(data) if data else None
        )

        if self.timeout:
            timer = reactor.callLater(self.timeout, self.abort_request,
                agent)

            def timeoutProxy(request):
                if timer.active():
                    timer.cancel()
                return self.response(request)

            def requestAborted(failure):
                if timer.active():
                    timer.cancel()

                failure.trap(defer.CancelledError,
                             error.ConnectingCancelledError)

                raise Timeout(
                    "Request took longer than %s seconds" % self.timeout)

            agent.addCallback(timeoutProxy).addErrback(requestAborted)
        else:
            agent.addCallback(self.response)

        return agent


    def getBody(self, url, method='GET', headers={}, data=None):
        """Make an HTTP request and return the body
        """

        if not 'User-Agent' in headers:
            headers['User-Agent'] = ['Tensor HTTP checker']

        return self.request(url, method, headers, data)

    @defer.inlineCallbacks
    def getJson(self, url, method='GET', headers={}, data=None):
        """Fetch a JSON result via HTTP
        """
        if not 'Content-Type' in headers:
            headers['Content-Type'] = ['application/json']

        body = yield self.getBody(url, method, headers, data)
        
        defer.returnValue(json.loads(body))
