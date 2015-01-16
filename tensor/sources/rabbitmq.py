import time

from zope.interface import implements

from twisted.internet import defer
from twisted.python import log

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork

class Queues(Source):
    """Returns Queue information for a particular vhost

    **Configuration arguments:**

    :param vhost: Vhost name
    :type vhost: str.

    **Metrics:**

    :(service_name).(queue).ready: Ready messages for queue
    :(service_name).(queue).unack: Unacknowledged messages for queue
    :(service_name).(queue).ready_rate: Ready rate of change per second
    :(service_name).(queue).unack_rate: Unacknowledge rate of change per second

    """
    implements(ITensorSource)

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        self.last_t = None

        self.ready = {}
        self.unack = {}

        self.last_ready = 0
        self.last_unack = 0

    @defer.inlineCallbacks
    def get(self):
        vhost = self.config.get('vhost', '/')

        mqctl = self.config.get('rabbitmqctl', '/usr/sbin/rabbitmqctl')

        out, err, code = yield fork(mqctl, args=(
            'list_queues', '-p', vhost, 'name', 'messages_ready',
            'messages_unacknowledged'
        ))

        if code == 0:
            t = time.time()

            total_ready = 0
            total_unack = 0

            rows = out.strip('\n').split('\n')[1:-1]

            events = []

            for row in rows:
                name, ready, unack = row.split()
                ready = int(ready)
                unack = int(unack)

                total_ready += ready
                total_unack += unack

                events.extend([
                    self.createEvent('ok', '%s unacknowledged messages: %s' % (
                        name, unack), unack, prefix='%s.unack' % name),
                    self.createEvent('ok', '%s ready messages: %s' % (
                        name, ready), ready, prefix='%s.ready' % name)
                ])

                if name in self.ready:
                    last_ready = self.ready[name]
                    last_unack = self.unack[name]

                    rrate = (ready - last_ready)/float(t - self.last_t)
                    urate = (unack - last_unack)/float(t - self.last_t)

                    events.extend([
                        self.createEvent('ok', '%s unacknowledged rate: %0.2f' % (
                            name, urate), urate, prefix='%s.unack_rate' % name),
                        self.createEvent('ok', '%s ready rate: %0.2f' % (
                            name, rrate), rrate, prefix='%s.ready_rate' % name)
                    ])

                self.ready[name] = ready
                self.unack[name] = unack

            if self.last_t:
                # Get total rates
                rrate = (total_ready - self.last_ready)/float(t - self.last_t)
                urate = (total_unack - self.last_unack)/float(t - self.last_t)

                events.extend([
                    self.createEvent('ok', 
                        'Total unacknowledged rate: %0.2f' % urate,
                        urate, prefix='total.unack_rate'),
                    self.createEvent('ok', 
                        'Total ready rate: %0.2f' % rrate,
                        rrate, prefix='total.ready_rate'),
                    self.createEvent('ok', 
                        'Total unacknowledged messages: %s' % total_unack,
                        total_unack, prefix='total.unack'),
                    self.createEvent('ok', 
                        'Total ready messages: %s' % total_ready,
                        total_ready, prefix='total.ready')
                ])

            self.last_ready = total_ready
            self.last_unack = total_unack

            self.last_t = t

            defer.returnValue(events)
        else:
            log.msg('Error running rabbitmqctl: ' + repr(err))
