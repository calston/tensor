"""
.. module:: snmp
   :platform: Unix
   :synopsis: A source module for polling SNMP. Requires PySNMP4

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time

from twisted.internet import reactor, defer

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor import aggregators

from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413.twisted import cmdgen
from pysnmp.carrier.twisted import dispatch
from pysnmp.carrier.twisted.dgram import udp
from pysnmp.proto import rfc1905, rfc1902


class SNMPConnection(object):
    """A wrapper class for PySNMP functions

    :param host: SNMP agent host
    :type host: str.
    :param port: SNMP port
    :type port: int.
    :param community: SNMP read community
    :type community: str.

    (This is not a source and you shouldn't try to use it as one)
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

    :param ip: SNMP agent host (default: 127.0.0.1)
    :type ip: str.
    :param port: SNMP port (default: 161)
    :type port: int.
    :param community: SNMP read community
    :type community: str.
    """

    implements(ITensorSource)
    def __init__(self, *a, **kw):
        Source.__init__(self, *a, **kw)

        host = self.config.get('ip', '127.0.0.1')
        port = int(self.config.get('port', 161))

        # Must add v3 support

        community = self.config.get('community', None)
        self.snmp = SNMPConnection(host, port, community)
    
    def getCounter(self, soid):
        return self.snmp.walk(soid)

    @defer.inlineCallbacks
    def getIfMetrics(self):
        ifaces = yield self.snmp.walk('1.3.6.1.2.1.2.2.1.2')

        table = [
            ('1.3.6.1.2.1.2.2.1.10', 'ifInOctets'),
            ('1.3.6.1.2.1.2.2.1.11', 'ifInUcastPkts'),
            ('1.3.6.1.2.1.2.2.1.12', 'ifInNUcastPkts'),
            ('1.3.6.1.2.1.2.2.1.14', 'ifInErrors'),
            ('1.3.6.1.2.1.2.2.1.13', 'ifInDiscards'),
            ('1.3.6.1.2.1.2.2.1.16', 'ifOutOctets'),
            ('1.3.6.1.2.1.2.2.1.17', 'ifOutUcastPkts'),
            ('1.3.6.1.2.1.2.2.1.18', 'ifOutNUcastPkts'),
            ('1.3.6.1.2.1.2.2.1.20', 'ifOutErrors'),
            ('1.3.6.1.2.1.2.2.1.19', 'ifOutDiscards'),
        ]
        
        data = {}
        for oid, key in table:
            d = yield self.getCounter(oid)
            for i, v in enumerate(d):
                noid, val = v

                if val:
                    iface = str(ifaces[i][1])
                    if not iface in data:
                        data[iface] = {}
                    data[iface][key] = val

        events = []

        for iface, metrics in data.items():
            for key, val in metrics.items():
                aggr = None

                if isinstance(val, rfc1902.Counter32):
                    aggr = aggregators.Counter32

                if isinstance(val, rfc1902.Counter64):
                    aggr = aggregators.Counter64

                events.append(
                    self.createEvent('ok',
                        "SNMP interface %s %s=%0.2f" % (iface, key, int(val)),
                        int(val),
                        prefix="%s.%s" % (iface, key), aggregation=aggr))

        defer.returnValue(events)

    @defer.inlineCallbacks
    def get(self):
        events = yield self.getIfMetrics()
        defer.returnValue(events)

class SNMPCisco837(SNMP):
    """Connects to a Cisco 837 and makes metrics

    **Configuration arguments:**

    :param ip: SNMP agent host (default: 127.0.0.1)
    :type ip: str.
    :param port: SNMP port (default: 161)
    :type port: int.
    :param community: SNMP read community
    :type community: str.
    """

    @defer.inlineCallbacks
    def get(self):

        events = yield self.getIfMetrics()

        sync_us = (yield self.snmp.walk('1.3.6.1.2.1.10.94.1.1.5'))[0][1]
        sync_ds = (yield self.snmp.walk('1.3.6.1.2.1.10.94.1.1.4'))[0][1]

        sync_us = int(sync_us)
        sync_ds = int(sync_ds)

        events.append(
            self.createEvent('ok', "SNMP ADSL sync downstream %s" % sync_ds,
                sync_ds, prefix="adsl.rxrate"))

        events.append(
            self.createEvent('ok', "SNMP ADSL sync upstream %s" % sync_us,
                sync_us, prefix="adsl.txrate"))

        link = yield self.snmp.walk('1.3.6.1.2.1.10.94.1.1.3')
        link = dict([(str(i), j) for i, j in link])

        output = int(link['1.3.6.1.2.1.10.94.1.1.3.1.7.15'])/10.0
        attn = int(link['1.3.6.1.2.1.10.94.1.1.3.1.5.15'])/10.0
        margin = int(link['1.3.6.1.2.1.10.94.1.1.3.1.4.15'])/10.0

        events.append(
            self.createEvent('ok', "SNMP ADSL output power %0.2fdBm" % output,
                output, prefix="adsl.outpwr"))

        events.append(
            self.createEvent('ok', "SNMP ADSL attenuation %0.2fdB" % attn,
                attn, prefix="adsl.attn"))

        events.append(
            self.createEvent('ok', "SNMP ADSL noise margin %0.2fdB" % margin,
                margin, prefix="adsl.margin"))
        
        defer.returnValue(events)
