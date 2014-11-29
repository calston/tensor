"""
.. module:: sflow
   :platform: Unix
   :synopsis: A source module which provides an sflow collector

.. moduleauthor:: Colin Alston <colin@imcol.in>
"""

import time

from twisted.internet import defer, reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from zope.interface import implements

from tensor.interfaces import ITensorSource
from tensor.objects import Source

from tensor.protocol.sflow import server
from tensor.protocol.sflow.protocol import flows, counters

class sFlowReceiver(server.DatagramReceiver):
    """sFlow datagram protocol"""
    def __init__(self, source):
        self.source = source
        self.counterCache = {}
        self.convoQueue = {}

    def receive_flow(self, flow, sample):
        if isinstance(sample, flows.IPv4Header):
            sport, dport = (sample.ip_sport, sample.ip_dport)
            src, dst = (sample.ip.src.asString(), sample.ip.dst.asString())
            bytes = sample.ip.total_length

            if not flow.if_inIndex in self.convoQueue:
                self.convoQueue[flow.if_inIndex] = []

            self.convoQueue[flow.if_inIndex].append(
                (src, sport, dst, dport, bytes))

    def process_convo_queue(self, queue, idx, deltaIn, tDelta):
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
                        prefix='%s.ip.%s.%s' % (idx, ip, direction)
                    )
                )

        for direction, v in port.items():
            for port, bytes in v.items():
                m = ((bytes/float(btotal)) * deltaIn)/tDelta

                self.source.queueBack(
                    self.source.createEvent('ok', 
                        'sFlow if:%s port:%s inOctets/sec %0.2f' % (
                            idx, port, m),
                        m,
                        prefix='%s.port.%s.%s' % (idx, port, direction)
                    )
                )

    def receive_counter(self, counter):

        idx = counter.if_index

        if idx in self.counterCache:
            lastIn, lastOut, lastT = self.counterCache[idx]
            tDelta = time.time() - lastT

            self.counterCache[idx] = (
                counter.if_inOctets, counter.if_outOctets, time.time())

            deltaOut = counter.if_outOctets - lastOut
            deltaIn = counter.if_inOctets - lastIn

            inRate = deltaIn / tDelta
            outRate = deltaOut / tDelta

            # Grab the queue for this interface
            if idx in self.convoQueue:
                queue = self.convoQueue[idx]
                self.convoQueue[idx] = []
                self.process_convo_queue(queue, idx, deltaIn, tDelta)

            self.source.queueBack([
                self.source.createEvent('ok', 
                    'sFlow index %s inOctets/sec %0.2f' % (idx, inRate),
                    inRate,
                    prefix='%s.inOctets' % idx),

                self.source.createEvent('ok', 
                    'sFlow index %s outOctets/sec %0.2f' % (idx, outRate),
                    outRate,
                    prefix='%s.outOctets' % idx),
            ])

        else:
            self.counterCache[idx] = (
                counter.if_inOctets, counter.if_outOctets, time.time())

class sFlow(Source):
    """Provides an sFlow server Source

    **Configuration arguments:**
    
    :port: UDP port to listen on
    :type method: int.
    :: A text string to match in the document when it is correct
    :type match: str.
    :useragent: User-Agent header to use
    :type useragent: str.

    **Metrics:**

    :(service name).latency: Time to complete request
    """

    implements(ITensorSource)

    def get(self):
        pass

    def startTimer(self):
        reactor.listenUDP(self.config.get('port', 6343), sFlowReceiver(self))
