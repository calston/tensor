import socket
import time
import fcntl
import random
import struct

from zope.interface import implements

from twisted.internet import task, defer, reactor, udp
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.interfaces import ISystemHandle

# OMG SHUT UP
class STFU(object):
    msg = lambda x, y: None
udp.log = STFU()

class IP(object):
    """IP header decoder
    """
    def __init__(self, packet):
        self.readPacket(packet)

    def readPacket(self, packet):
        vl = struct.unpack('!b', packet[0])[0]
        l = (vl & 0xf) * 4

        head = packet[:l]
        self.offset = struct.unpack('!H', packet[6:8])

        self.payload = packet[l:]

class EchoPacket(object):
    """ICMP Echo packet encoder and decoder
    """
    def __init__(self, seq=0, id=None, data=None, packet=None):
        if packet:
            self.decodePacket(packet)
            self.packet = packet
        else:
            self.id = id
            self.seq = seq
            self.data = data
            self.encodePacket()

    def calculateChecksum(self, buffer):
        nleft = len(buffer)
        sum = 0
        pos = 0
        while nleft > 1:
            sum = ord(buffer[pos]) * 256 + (ord(buffer[pos + 1]) + sum)
            pos = pos + 2
            nleft = nleft - 2
        if nleft == 1:
            sum = sum + ord(buffer[pos]) * 256

        sum = (sum >> 16) + (sum & 0xFFFF)
        sum += (sum >> 16)
        sum = (~sum & 0xFFFF)

        return sum

    def encodePacket(self):
        head = struct.pack('!bb', 8, 0)

        echo = struct.pack('!HH', self.seq, self.id)

        chk = self.calculateChecksum(
            head + '\x00\x00' + echo + self.data)

        chk = struct.pack('!H', chk)

        self.packet = head + chk + echo + self.data

    def decodePacket(self, packet):
        self.type, self.code, self.chk, self.seq, self.id = struct.unpack(
            '!bbHHH', packet[:8])

        self.data = packet[8:]

        rc = '%s\x00\x00%s' % (packet[:2], packet[4:])
        mychk = self.calculateChecksum(rc)

        if mychk == self.chk:
            self.valid = True
        else:
            self.valid = False

    def __repr__(self):
        return "<type=%s code=%s chk=%s seq=%s data=%s valid=%s>" % (
            self.type, self.code, self.chk, self.seq, len(self.data), self.valid)

class ICMPPing(DatagramProtocol):
    """ICMP Ping implementation
    """
    noisy=False
    def __init__(self, d, dst, count, inter=0.2, maxwait=1000, size=64):
        self.deferred = d
        self.dst = dst
        self.size = size - 36
        self.count = count
        self.seq = 0
        self.start = 0
        self.id_base = random.randint(0, 40000)
        self.maxwait = maxwait
        self.inter = inter

        self.t = task.LoopingCall(self.ping)
        self.recv = []

    def datagramReceived(self, datagram, address):
        now = int(time.time()*1000000)
        host, port = address

        packet = IP(datagram)

        icmp = EchoPacket(packet=packet.payload)

        if icmp.valid and icmp.code==0 and icmp.type==0:
            # Check ID is from this pinger
            if (icmp.id-icmp.seq) == self.id_base:
                ts = icmp.data[:8]
                data = icmp.data[8:]
                delta = (now - struct.unpack('!Q', ts)[0])/1000.0

                self.maxwait = (self.maxwait + delta)/2.0

                self.recv.append((icmp.seq, delta))

    def createData(self, n):
        s = ""
        c = 33
        for i in range(n):
            s += chr(c)
            if c < 126:
                c += 1
            else:
                c = 33
        return s

    def sendEchoRequest(self):
        # Pack the packet with an ascii table
        md = self.createData(self.size)

        us = int(time.time()*1000000)
        data = '%s%s' % (struct.pack('!Q', us), md)

        pkt = EchoPacket(seq=self.seq, id=self.id_base+self.seq, data=data)

        self.transport.write(pkt.packet)
        self.seq += 1

    def ping(self):
        if self.seq < self.count:
            self.sendEchoRequest()
        else:
            self.t.stop()

            tdelay = (self.maxwait * self.count)/1000.0
            elapsed = time.time() - self.start
            remaining = tdelay - elapsed
            if remaining < 0.05:
                remaining = 0.05

            reactor.callLater(remaining, self.endPing)

    def endPing(self):
        r = len(self.recv)
        loss = (self.count - r) / float(self.count)
        loss = int(100*loss)
        if r:
            avgLatency = sum([i[1] for i in self.recv]) / float(r)
        else:
            avgLatency = None

        self.deferred.callback((loss, avgLatency))

    def startPing(self):
        self.transport.connect(self.dst, random.randint(33434, 33534))
        self.start = time.time()
        self.t.start(self.inter)

    def startProtocol(self):
        self.startPing()

class ICMPPort(udp.Port):
    """Raw socket listener for ICMP
    """
    implements(ISystemHandle)

    maxThroughput = 256 * 1024

    def createInternetSocket(self):
        s = socket.socket(
            socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

        s.setblocking(0)

        fd = s.fileno()

        # Set close-on-exec

        flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        flags = flags | fcntl.FD_CLOEXEC
        fcntl.fcntl(fd, fcntl.F_SETFD, flags)

        return s

def ping(dst, count, inter=0.2, maxwait=1000, size=64):
    """Sends ICMP echo requests to destination `dst` `count` times.
    Returns a deferred which fires when responses are finished.
    """
    def _then(result, p):
        p.stopListening()
        return result

    d = defer.Deferred()
    p = ICMPPort(0, ICMPPing(d, dst, count, inter, maxwait, size), "", 8192, reactor)
    p.startListening()

    return d.addCallback(_then, p)
