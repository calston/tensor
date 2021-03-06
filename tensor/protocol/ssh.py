from twisted.conch.ssh.keys import EncryptedKeyError, Key
from twisted.conch.client.knownhosts import KnownHostsFile
from twisted.conch.endpoints import SSHCommandClientEndpoint

from twisted.internet import defer, protocol, endpoints, reactor, error

from twisted.python.compat import nativeString
from twisted.python.filepath import FilePath
from twisted.python import log

# Monkey patch noisy logs
class FakeLog(object):
    def msg(self, *a):
        pass

    def callWithLogger(self, *a, **kw):
        return log.callWithLogger(*a, **kw)
from twisted.conch.ssh import connection, channel
connection.log = FakeLog()
channel.log = FakeLog()

try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO


class SSHCommandProtocol(protocol.Protocol):
    def connectionMade(self):
        self.finished = defer.Deferred()
        self.stdOut = StringIO()
        self.stdErr = StringIO()

    def dataReceived(self, data):
        self.stdOut.write(data.decode())

    def extReceived(self, code, data):
        self.stdErr.write(data.decode())

    def connectionLost(self, reason):
        self.stdOut.seek(0)
        self.stdErr.seek(0)
        if reason.type is error.ConnectionDone:
            # Success
            code = 0
        else:
            code = reason.value.exitCode
        self.factory.done.callback((self.stdOut, self.stdErr, code))

class SSHClient(object):
    def __init__(self, hostname, username, port, password=None,
                 knownhosts=None):

        self.hostname = hostname.encode()
        self.username = username.encode()
        self.port = int(port)
        self.password = None
        if password:
            self.password = password.encode()
        self.connection = None

        if not knownhosts:
            knownhosts = '/var/lib/tensor/known_hosts'

        self.knownHosts = KnownHostsFile.fromPath(FilePath(knownhosts.encode()))
        self.knownHosts.verifyHostKey = self.verifyHostKey

        self.keys = []

    def verifyHostKey(self, ui, hostname, ip, key):
        hhk = defer.maybeDeferred(self.knownHosts.hasHostKey, hostname, key)
        def gotHasKey(result):
            if result:
                if not self.knownHosts.hasHostKey(ip, key):
                    log.msg("Added new %s host key for IP address '%s'." %
                            (key.type(), nativeString(ip)))
                    self.knownHosts.addHostKey(ip, key)
                    self.knownHosts.save()
                return result
            else:
                log.msg("Added %s host key for IP address '%s'." %
                        (key.type(), nativeString(ip)))
                self.knownHosts.addHostKey(hostname, key)
                self.knownHosts.addHostKey(ip, key)
                self.knownHosts.save()
                return True
        return hhk.addCallback(gotHasKey)

    def addKeyFile(self, kfile, password=None):
        if not os.path.exists(kfile):
            raise Exception("Key file not found %s", kfile)

        try:
            self.keys.append(Key.fromFile(kfile))
        except EncryptedKeyError:
            self.keys.append(Key.fromFile(kfile, passphrase=password))
        
    def addKeyString(self, kstring, password=None):
        try:
            self.keys.append(Key.fromString(kstring))
        except EncryptedKeyError:
            self.keys.append(Key.fromString(kstring, passphrase=password))

    def _get_endpoint(self):
        """ Creates a generic endpoint connection that doesn't finish
        """
        return SSHCommandClientEndpoint.newConnection(
            reactor, b'/bin/cat', self.username, self.hostname,
            port=self.port, keys=self.keys, password=self.password,
            knownHosts = self.knownHosts)

    def connect(self):
        log.msg("Opening SSH connection to %s@%s:%s" % (
            self.username, self.hostname, self.port))

        self.endpoint = self._get_endpoint()
        factory = protocol.Factory()
        factory.protocol = protocol.Protocol

        def connected(protocol):
            log.msg("Established SSH connection to %s" % (
                self.hostname,))
            self.connection = protocol.transport.conn

        d = self.endpoint.connect(factory)
        d.addCallback(connected)

        return d

    def fork(self, command, args=(), env={}, path=None, timeout=3600):
        if not self.connection:
            log.msg("Connection to %s not yet ready" % (
                self.hostname,))

            return defer.maybeDeferred(lambda: (None, "SSH not ready", 255))

        if env:
            env = ' '.join('%s=%s' % (k, v) for k, v in env.items()) + ' '
        else:
            env = ''

        if args:
            args = ' ' + ' '.join(args)
        else:
            args = ''

        e = SSHCommandClientEndpoint.existingConnection(self.connection,
                (env + command + args).encode())

        factory = protocol.Factory()
        factory.protocol = SSHCommandProtocol
        factory.done = defer.Deferred()

        def finished(result):
            stdout, stderr, code = result
            return (stdout.read(), stderr.read(), code)

        factory.done.addCallback(finished)

        def connected(connection):
            # Be nice if Conch exposed this better...
            connection.transport.extReceived = connection.extReceived
            return factory.done

        return e.connect(factory).addCallback(connected)
