import time

from zope.interface import implements

from twisted.internet import defer
from twisted.python import log

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork

class Queues(Source):
    """Query llen from redis-cli

    **Configuration arguments:**

    :param queue: Queue name (defaults to 'celery', just because)
    :type queue: str.
    :param db: DB number
    :type db: int.
    :param clipath: Path to redis-cli (default: /usr/bin/redis-cli)
    :type clipath: str.

    **Metrics:**

    :(service_name): Queue length
    """
    implements(ITensorSource)

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        self.queue = self.config.get('queue', 'celery')
        self.db = int(self.config.get('db', 0))

        self.clipath = self.config.get('clipath', '/usr/bin/redis-cli')

    @defer.inlineCallbacks
    def get(self):

        out, err, code = yield fork(self.clipath,
            args=('-n', self.db, 'llen', self.queue,)
        )

        events = []
        if code == 0:
            val = int(out.strip('\n').split()[-1])

            defer.returnValue(
                self.createEvent('ok', '%s queue length' % self.queue, val)
            )

        else:
            err = 'Error running %s: %s' % (self.clipath, repr(err))
            log.msg(err)
            defer.returnValue(
                self.createEvent('critical', err, None)
            )
