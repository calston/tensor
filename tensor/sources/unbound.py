from zope.interface import implementer

from twisted.internet import defer
from twisted.python import log

from tensor.interfaces import ITensorSource
from tensor.objects import Source


@implementer(ITensorSource)
class Stats(Source):
    """Returns stats from unbound-control

    **Configuration arguments:**

    :param executable: Path to unbound-control executable 
                       (default: /usr/sbin/unbound-control)
    :type executable: str.

    """
    ssh = True

    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        self.uc = self.config.get('executable', '/usr/sbin/unbound-control')

    @defer.inlineCallbacks
    def _get_uc_stats(self):
        out, err, code = yield self.fork(self.uc, args=('stats', ))
        
        if code == 0:
            defer.returnValue(out.strip('\n').split('\n'))
        else:
            log.msg('Error running unbound-control: ' + repr(err))
            defer.returnValue([])

    @defer.inlineCallbacks
    def get(self):
        events = []
        
        stats = yield self._get_uc_stats()

        for row in stats:
            key, val = row.split('=')
            
            try:
                val = float(val)
            except:
                # Not a number
                continue 

            events.append(self.createEvent('ok', key, val, prefix=key))

        defer.returnValue(events)
