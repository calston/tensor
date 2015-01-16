"""
.. module:: sflow
   :platform: Unix
   :synopsis: A source module which provides an sflow collector

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time

from twisted.internet import defer, reactor
from twisted.names import client

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor import utils

from tensor.protocol.sflow import server
from tensor.protocol.sflow.protocol import flows, counters


class sFlowReceiver(server.DatagramReceiver):
    """sFlow datagram protocol
    """
    def __init__(self, source):
        self.source = source
        self.lookup = source.config.get('dnslookup', True)
        self.counterCache = {}
        self.convoQueue = {}

        self.resolver = utils.Resolver()

    def process_convo_queue(self, queue, host, idx, deltaIn, tDelta):
        cn_bytes = sum(map(lambda i: i[4], queue))

        addr = {'dst':{}, 'src': {}}
        port = {'dst':{}, 'src': {}}

        btotal = 0

        # Try and aggregate chunks of flow information into something that 
        # is actually useful in Riemann and InfluxDB.
        for convo in queue:
            src, sport, dst, dport, bytes = convo

            if not src in addr['src']:
                addr['src'][src] = 0

            if not dst in addr['dst']:
                addr['dst'][dst] = 0

            btotal += bytes
            addr['src'][src] += bytes
            addr['dst'][dst] += bytes

            if not sport in port['src']:
                port['src'][sport] = 0

            if not dport in port['dst']:
                port['dst'][dport] = 0

            port['src'][sport] += bytes
            port['dst'][dport] += bytes

        for direction, v in addr.items():
            for ip, bytes in v.items():
                m = ((bytes/float(btotal)) * deltaIn)/tDelta

                self.source.queueBack(
                    self.source.createEvent('ok', 
                        'sFlow if:%s addr:%s inOctets/sec %0.2f' % (
                            idx, ip, m),
                        m,
                        prefix='%s.ip.%s.%s' % (idx, ip, direction),
                        hostname=host
                    )
                )

        for direction, v in port.items():
            for port, bytes in v.items():
                m = ((bytes/float(btotal)) * deltaIn)/tDelta

                if port:
                    self.source.queueBack(
                        self.source.createEvent('ok', 
                            'sFlow if:%s port:%s inOctets/sec %0.2f' % (
                                idx, port, m),
                            m,
                            prefix='%s.port.%s.%s' % (idx, port, direction),
                            hostname=host
                        )
                    )

    def receive_flow(self, flow, sample, host):
        def queueFlow(host):
            if isinstance(sample, flows.IPv4Header):
                if sample.ip.proto in ('TCP', 'UDP'):
                    sport, dport = (sample.ip_sport, sample.ip_dport)
                else:
                    sport, dport = (None, None)

                src, dst = (sample.ip.src.asString(), sample.ip.dst.asString())
                bytes = sample.ip.total_length

                if not host in self.convoQueue:
                    self.convoQueue[host] = {}

                if not flow.if_inIndex in self.convoQueue[host]:
                    self.convoQueue[host][flow.if_inIndex] = []

                self.convoQueue[host][flow.if_inIndex].append(
                    (src, sport, dst, dport, bytes))

        if self.lookup:
            return self.resolver.reverse(host).addCallback(
                queueFlow).addErrback(queueFlow)
        else:
            return queueFlow(None, host)

    def receive_counter(self, counter, host):
        def _hostcb(host):
            idx = counter.if_index

            if not host in self.convoQueue:
                self.convoQueue[host] = {}

            if not host in self.counterCache:
                self.counterCache[host] = {}

            if idx in self.counterCache[host]:
                lastIn, lastOut, lastT = self.counterCache[host][idx]
                tDelta = time.time() - lastT

                self.counterCache[host][idx] = (
                    counter.if_inOctets, counter.if_outOctets, time.time())

                deltaOut = counter.if_outOctets - lastOut
                deltaIn = counter.if_inOctets - lastIn

                inRate = deltaIn / tDelta
                outRate = deltaOut / tDelta

                # Grab the queue for this interface
                if idx in self.convoQueue[host]:
                    queue = self.convoQueue[host][idx]
                    self.convoQueue[host][idx] = []
                    self.process_convo_queue(queue, host, idx, deltaIn, tDelta)

                self.source.queueBack([
                    self.source.createEvent('ok', 
                        'sFlow index %s inOctets/sec %0.2f' % (idx, inRate),
                        inRate,
                        prefix='%s.inOctets' % idx, hostname=host),

                    self.source.createEvent('ok', 
                        'sFlow index %s outOctets/sec %0.2f' % (idx, outRate),
                        outRate,
                        prefix='%s.outOctets' % idx, hostname=host),
                ])

            else:
                self.counterCache[host][idx] = (
                    counter.if_inOctets, counter.if_outOctets, time.time())

        if self.lookup:
            return self.resolver.reverse(host).addCallback(
                _hostcb).addErrback(_hostcb)
        else:
            return _hostcb(None, host)

class sFlow(Source):
    """Provides an sFlow server Source

    **Configuration arguments:**
    
    :param port: UDP port to listen on
    :type port: int.
    :param dnslookup: Enable reverse DNS lookup for device IPs (default: True)
    :type dnslookup: bool.

    **Metrics:**
    
    Metrics are published using the key patterns 
    (device).(service name).(interface).(in|out)Octets
    (device).(service name).(interface).ip
    (device).(service name).(interface).port
    """

    implements(ITensorSource)

    def get(self):
        pass

    def startTimer(self):
        """Creates a sFlow datagram server
        """
        reactor.listenUDP(self.config.get('port', 6343), sFlowReceiver(self))
