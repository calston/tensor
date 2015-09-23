import signal
import json
import time
import urllib
import exceptions
import os

from StringIO import StringIO

from zope.interface import implements

from twisted.internet import reactor, protocol, defer, error
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.web.client import Agent
from twisted.names import client
from twisted.python import log

from twisted.internet.endpoints import clientFromString

class SocketyAgent(Agent):
    def __init__(self, reactor, path, **kwargs):
        self.path = path
        Agent.__init__(self, reactor, **kwargs)

    def _getEndpoint(self, scheme, host, port):
        client = clientFromString(reactor, self.path)
        return client

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

try:
    from twisted.internet.ssl import ClientContextFactory

    class WebClientContextFactory(ClientContextFactory):
        def getContext(self, hostname, port):
            return ClientContextFactory.getContext(self)
    SSL=True
except:
    SSL=False

try:
    from twisted.web import client
    client._HTTP11ClientFactory.noisy = False
    client.HTTPClientFactory.noisy = False
except:
    pass

class HTTPRequest(object):
    def __init__(self, timeout=120):
        self.timeout = timeout

    def abort_request(self, request):
        """Called to abort request on timeout"""
        self.timedout = True
        if not request.called:
            try:
                request.cancel()
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

    def request(self, url, method='GET', headers={}, data=None, socket=None):
        self.timedout = False

        if socket:
            agent = SocketyAgent(reactor, socket)
        else:
            if url[:5] == 'https':
                if SSL:
                    agent = Agent(reactor, WebClientContextFactory())
                else:
                    raise Exception('HTTPS requested but not supported')
            else:
                agent = Agent(reactor)
        
        request = agent.request(method, url,
            Headers(headers),
            StringProducer(data) if data else None
        )

        if self.timeout:
            timer = reactor.callLater(self.timeout, self.abort_request,
                request)

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

            request.addCallback(timeoutProxy).addErrback(requestAborted)
        else:
            request.addCallback(self.response)

        return request


    def getBody(self, url, method='GET', headers={}, data=None, socket=None):
        """Make an HTTP request and return the body
        """

        if not 'User-Agent' in headers:
            headers['User-Agent'] = ['Tensor HTTP checker']

        return self.request(url, method, headers, data, socket)

    @defer.inlineCallbacks
    def getJson(self, url, method='GET', headers={}, data=None, socket=None):
        """Fetch a JSON result via HTTP
        """
        if not 'Content-Type' in headers:
            headers['Content-Type'] = ['application/json']

        body = yield self.getBody(url, method, headers, data, socket)
        
        defer.returnValue(json.loads(body))

class PersistentCache(object):
    """A very basic dictionary cache abstraction. Not to be used
    for large amounts of data or high concurrency"""

    def __init__(self, location='/var/lib/tensor/cache'):
        self.store = {}
        self.location = location
        self.mtime = 0
        self._read()

    def _changed(self):
        if os.path.exists(self.location):
            mtime = os.stat(self.location).st_mtime

            return self.mtime != mtime
        else:
            return False

    def _acquire_cache(self):
        try:
            cache_file = open(self.location, 'r')
        except exceptions.IOError:
            return {}

        cache = json.loads(cache_file.read())
        cache_file.close()
        return cache

    def _write_cache(self, d):
        cache_file = open(self.location, 'w')
        cache_file.write(json.dumps(d))
        cache_file.close()

    def _persist(self):
        cache = self._acquire_cache()

        for k, v in self.store.iteritems():
            cache[k] = v

        self._write_cache(cache)

    def _read(self):
        cache = self._acquire_cache()
        for k, v in cache.iteritems():
            self.store[k] = v

    def _remove_key(self, k):
        cache = self._acquire_cache()
        if k in cache:
            if k in cache:
                del cache[k]
            if k in self.store:
                del self.store[k]
            self._write_cache(cache)

    def expire(self, age):
        """Expire any items in the cache older than `age` seconds"""
        now = time.time()
        cache = self._acquire_cache()
        
        expired = [k for k, v in cache.iteritems() if (now - v[0]) > age]

        for k in expired:
            if k in cache:
                del cache[k]
            if k in self.store:
                del self.store[k]

        self._write_cache(cache)

    def set(self, k, v):
        """Set a key `k` to value `v`"""
        self.store[k] = (time.time(), v)
        self._persist()

    def get(self, k):
        """Returns key contents, and modify time"""
        if self._changed():
            self._read()

        if k in self.store:
            return tuple(self.store[k])
        else:
            return None

    def contains(self, k):
        """Return True if key `k` exists"""
        if self._changed():
            self._read()
        return k in self.store.keys()

    def delete(self, k):
        """Remove key `k` from the cache"""
        self._remove_key(k)

