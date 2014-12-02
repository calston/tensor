import time

from twisted.internet import reactor, defer

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413.twisted import cmdgen
from pysnmp.carrier.twisted import dispatch
from pysnmp.carrier.twisted.dgram import udp
from pysnmp.proto import rfc1905


class SNMPConnection(object):
    """A wrapper class for PySNMP functions
    """
    
    def __init__(self, host, port, community):
        self.snmp = engine.SnmpEngine()
        self.snmp.registerTransportDispatcher(dispatch.TwistedDispatcher())

        config.addV1System(self.snmp, 'my-area', community)
        config.addTargetParams(self.snmp,
            'my-creds', 'my-area', 'noAuthNoPriv', 0)
        config.addSocketTransport(self.snmp,
            udp.domainName, udp.UdpTwistedTransport().openClientMode()
        )
        config.addTargetAddr(self.snmp, 'my-router', udp.domainName,
            (host, port), 'my-creds')

    def _walk(self, soid):
        # Error/response receiver
        result = []
        def cbFun(cbCtx, result, d):
            (errorIndication, errorStatus, errorIndex, varBindTable) = cbCtx
            if errorIndication:
                print(errorIndication)
            elif errorStatus and errorStatus != 2:
                print('%s at %s' % (
                        errorStatus.prettyPrint(),
                        errorIndex and varBindTable[-1][int(errorIndex)-1][0] or '?'
                    )
                )
            else:
                for varBindRow in varBindTable:
                    for oid, val in varBindRow:
                        if str(oid).startswith(soid):
                            result.append((oid, val))

                for oid, val in varBindRow:
                    if not str(oid).startswith(soid):
                        d.callback(result)
                        return 
                    if not val.isSameTypeWith(rfc1905.endOfMibView):
                        break
                else:
                    d.callback(result)
                    return

                df = defer.Deferred()
                df.addCallback(cbFun, result, d)
                return df

            d.callback(result)

        # Prepare request to be sent yielding Twisted deferred object
        df = cmdgen.NextCommandGenerator().sendReq(self.snmp,
            'my-router', ((soid, None),))

        d = defer.Deferred()
        df.addCallback(cbFun, result, d)
        return d

    def walk(self, oid):
        return self._walk(oid)

class SNMP(Source):
    """Connects to an SNMP agent and retrieves OIDs

    **Configuration arguments:**

    :host: SNMP agent host (default: localhost)
    :type host: str.
    :port: SNMP port (default: 161)
    :type port: int.
    :community: SNMP read community
    :type community: str.
    """

    implements(ITensorSource)
    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        self.cache = {}

        host = self.config.get('host', 'localhost')
        port = int(self.config.get('port', 161))

        # Must add v3 support

        community = self.config.get('community', None)
        self.snmp = SNMPConnection(host, port, community)

    @defer.inlineCallbacks
    def get(self):

        ifaces = yield self.snmp.walk('1.3.6.1.2.1.2.2.1.2')
        ifInOctets = yield self.snmp.walk('1.3.6.1.2.1.2.2.1.10')
        ifOutOctets = yield self.snmp.walk('1.3.6.1.2.1.2.2.1.16')

        getVal =  lambda j: map(lambda i: i[1], j)

        values = zip(getVal(ifaces), getVal(ifInOctets), getVal(ifOutOctets))
            
        events = []
        for iface, inoct, outoct in values:
            if iface in self.cache:
                # Calculate the average rate over the last sample interval
                lastin, lastout, lastt = self.cache[iface]
                tDelta = time.time() - lastt
                irate = (inoct - lastin)/tDelta
                orate = (outoct - lastout)/tDelta

                self.cache[iface] = (inoct, outoct, time.time())

                # Send events
                events.append(
                    self.createEvent('ok',
                        "SNMP interface %s %0.2f in" % (iface, irate),
                        irate,
                        prefix="%s.ifInOctets" % iface))
                events.append(
                    self.createEvent('ok',
                        "SNMP interface %s %0.2f in" % (iface, orate),
                        orate,
                        prefix="%s.ifOutOctets" % iface))

            else:
                self.cache[iface] = (inoct, outoct, time.time())

        defer.returnValue(events)
