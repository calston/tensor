from zope.interface import implements

from twisted.internet import defer

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork

class StrongSwan(Source):
    """Returns the status of strongSwan IPSec tunnels

    **Metrics:**

    :(service name).(peer name): Tunnel status
    """
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        out, err, code = yield fork('/usr/bin/sudo', args=(
            'ipsec', 'statusall'))

        connections = {}

        s = 0

        for l in out.strip('\n').split('\n'):
            if l == "Connections:":
                s = 1
                continue
            elif l == "Routed Connections:":
                s = 2
            elif "Security Associations" in l:
                s = 3
            elif l[0] == ' ' and ':' in l:
                if s == 1:
                    con, detail = l.strip().split(': ', 1)
                    detail = detail.strip()

                    if con not in connections:
                        connections[con] = {
                            'source': detail.split('...')[0],
                            'destination': detail.split('...')[1].split()[0],
                            'up': False
                        }
                elif s == 3:
                    con, detail = l.strip().split(': ', 1)
                    detail = detail.strip()
                    if '[' in con:
                        con = con.split('[')[0]
                    else:
                        con = con.split('{')[0]

                    if 'ESTABLISHED' in detail:
                        connections[con]['up'] = True
    
        events = []
        for k, v in connections.items():
            if v['up']:
                events.append(self.createEvent('ok', 'IPSec tunnel %s up' % k,
                    1, prefix=k))
            else:
                events.append(self.createEvent('critical', 
                    'IPSec tunnel %s down' % k, 0, prefix=k))

        defer.returnValue(events)
