import hashlib
import re
import time
import socket

try:
    from exceptions import NotImplementedError
except ImportError:
    pass

from twisted.internet import task, defer
from twisted.python import log

from tensor.utils import fork
from tensor.protocol import ssh

class Event(object):
    """Tensor Event object

    All sources pass these to the queue, which form a proxy object
    to create protobuf Event objects

    :param state: Some sort of string < 255 chars describing the state
    :param service: The service name for this event
    :param description: A description for the event, ie. "My house is on fire!"
    :param metric: int or float metric for this event
    :param ttl: TTL (time-to-live) for this event
    :param tags: List of tag strings
    :param hostname: Hostname for the event (defaults to system fqdn)
    :param aggregation: Aggregation function
    :param attributes: A dictionary of key/value attributes for this event
    :param evtime: Event timestamp override
    """
    def __init__(
            self,
            state,
            service,
            description,
            metric,
            ttl,
            tags=None,
            hostname=None,
            aggregation=None,
            evtime=None,
            attributes=None,
            type='riemann'):
        self.state = state
        self.service = service
        self.description = description
        self.metric = metric
        self.ttl = ttl
        self.tags = tags if tags is not None else []
        self.attributes = attributes
        self.aggregation = aggregation
        self._type = type
        
        if evtime:
            self.time = evtime
        else:
            self.time = time.time()
        if hostname:
            self.hostname = hostname
        else:
            self.hostname = socket.gethostbyaddr(socket.gethostname())[0]

    def id(self):
        return self.hostname + '.' + self.service

    def __repr__(self):
        ser = ['%s=%s' % (k, repr(v)) for k,v in dict(self).items()]

        return "<Event %s>" % (', '.join(ser))

    def __iter__(self):
        d = {
            'hostname': self.hostname,
            'state': self.state,
            'service': self.service,
            'metric': self.metric,
            'ttl': self.ttl,
            'tags': self.tags,
            'time': self.time,
            'description': self.description,
        }
        for k, v in d.items():
            yield k, v

    def copyWithMetric(self, m):
        return Event(
            self.state, self.service, self.description, m, self.ttl, self.tags,
            self.hostname, self.aggregation
        )

class Output(object):
    """Output parent class

    Outputs can inherit this object which provides a construct
    for a working output

    :param config: Dictionary config for this queue (usually read from the
             yaml configuration)
    :param tensor: A TensorService object for interacting with the queue manager
    """
    def __init__(self, config, tensor):
        self.config = config
        self.tensor = tensor

    def createClient(self):
        """Deferred which sets up the output
        """
        pass

    def eventsReceived(self):
        """Receives a list of events and processes them

        Arguments:
        events -- list of `tensor.objects.Event`
        """
        pass

    def stop(self):
        """Called when the service shuts down
        """
        pass

class Source(object):
    """Source parent class

    Sources can inherit this object which provides a number of
    utility methods.

    :param config: Dictionary config for this queue (usually read from the
             yaml configuration)
    :param queueBack: A callback method to recieve a list of Event objects
    :param tensor: A TensorService object for interacting with the queue manager
    """

    sync = False
    ssh = False

    def __init__(self, config, queueBack, tensor):
        self.config = config
        self.tensor = tensor

        self.t = task.LoopingCall(self.tick)
        self.td = None
        self.attributes = None

        self.service = config['service']
        self.inter = float(config['interval'])
        self.ttl = float(config['ttl'])

        if 'tags' in config:
            self.tags = [tag.strip() for tag in config['tags'].split(',')]
        else:
            self.tags = []

        attributes = config.get("attributes")
        if isinstance(attributes, dict):
            self.attributes = attributes

        self.hostname = config.get('hostname')
        if self.hostname is None:
            self.hostname = socket.gethostbyaddr(socket.gethostname())[0]

        self.use_ssh = config.get('use_ssh', False)

        if self.use_ssh:
            self._init_ssh()

        self.queueBack = self._queueBack(queueBack)

        self.running = False

    def _init_ssh(self):
        """ Configure SSH client options
        """

        self.ssh_host = self.config.get('ssh_host', self.hostname)

        self.known_hosts = self.config.get('ssh_knownhosts_file',
            self.tensor.config.get('ssh_knownhosts_file', None))

        self.ssh_keyfile = self.config.get('ssh_keyfile',
            self.tensor.config.get('ssh_keyfile', None))

        self.ssh_key = self.config.get('ssh_key',
            self.tensor.config.get('ssh_key', None))

        # Not sure why you'd bother but maybe you've got a weird policy
        self.ssh_keypass = self.config.get('ssh_keypass',
            self.tensor.config.get('ssh_keypass', None))

        self.ssh_user = self.config.get('ssh_username',
            self.tensor.config.get('ssh_username', None))

        self.ssh_password = self.config.get('ssh_password',
            self.tensor.config.get('ssh_password', None))

        self.ssh_port = self.config.get('ssh_port',
            self.tensor.config.get('ssh_port', 22))

        # Verify config to see if we're good to go

        if not (self.ssh_key or self.ssh_keyfile or self.ssh_password):
            raise Exception("To use SSH you must specify *one* of ssh_key,"
                            " ssh_keyfile or ssh_password for this source"
                            " check or globally")

        if not self.ssh_user:
            raise Exception("ssh_username must be set")

        self.ssh_keydb = []

        cHash = hashlib.sha1(':'.join((
                        self.ssh_host, self.ssh_user, str(self.ssh_port),
                        str(self.ssh_password), str(self.ssh_key),
                        str(self.ssh_keyfile)
                    )).encode()).hexdigest()

        if cHash in self.tensor.hostConnectorCache:
            self.ssh_client = self.tensor.hostConnectorCache.get(cHash)
            self.ssh_connector = False
        else:
            self.ssh_connector = True
            self.ssh_client = ssh.SSHClient(self.ssh_host, self.ssh_user,
                    self.ssh_port, password=self.ssh_password,
                    knownhosts=self.known_hosts)

            if self.ssh_keyfile:
                self.ssh_client.addKeyFile(self.ssh_keyfile, self.ssh_keypass)

            if self.ssh_key:
                self.ssh_client.addKeyString(self.ssh_key, self.ssh_keypass)

            self.tensor.hostConnectorCache[cHash] = self.ssh_client

    def _queueBack(self, caller):
        return lambda events: caller(self, events)

    def startTimer(self):
        """Starts the timer for this source"""
        self.td = self.t.start(self.inter)

        if self.use_ssh and self.ssh_connector:
            self.ssh_client.connect()

    def stopTimer(self):
        """Stops the timer for this source"""
        self.td = None
        self.t.stop()

    def fork(self, *a, **kw):
        if self.use_ssh:
            return self.ssh_client.fork(*a, **kw)
        else:
            return fork(*a, **kw)

    @defer.inlineCallbacks
    def _get(self):
        if self.use_ssh and not self.ssh:
            event = yield defer.maybeDeferred(self.sshGet)

        else:
            event = yield defer.maybeDeferred(self.get)

        if self.config.get('debug', False):
            log.msg("[%s] Tick: %s" % (self.config['service'], event))

        defer.returnValue(event)

    @defer.inlineCallbacks
    def tick(self):
        """Called for every timer tick. Calls self.get which can be a deferred
        and passes that result back to the queueBack method
        
        Returns a deferred"""

        if self.sync:
            if self.running:
                defer.returnValue(None)

        self.running = True

        try:
            event = yield self._get()
            if event:
                self.queueBack(event)

        except Exception as e:
            log.msg("[%s] Unhandled error: %s" % (self.service, e))

        self.running = False

    def createEvent(self, state, description, metric, prefix=None,
            hostname=None, aggregation=None, evtime=None):
        """Creates an Event object from the Source configuration"""
        if prefix:
            service_name = self.service + "." + prefix
        else:
            service_name = self.service

        return Event(state, service_name, description, metric, self.ttl,
            hostname=hostname or self.hostname, aggregation=aggregation,
            evtime=evtime, tags=self.tags, attributes=self.attributes
        )

    def createLog(self, type, data, evtime=None, hostname=None):
        """Creates an Event object from the Source configuration"""

        return Event(None, type, data, 0, self.ttl,
            hostname=hostname or self.hostname, evtime=evtime, tags=self.tags, type='log'
        )

    def get(self):
        raise NotImplementedError()

    def sshGet(self):
        raise NotImplementedError("This source does not implement SSH remote checks")
