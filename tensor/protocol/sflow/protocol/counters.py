from construct import *
from construct import adapters

class InterfaceCounters(object):
    def __init__(self, u):
        self.if_index = u.unpack_uint()
        self.if_type = u.unpack_uint()
        self.if_speed = u.unpack_uhyper()

        self.if_mode = u.unpack_uint()
        self.if_status = u.unpack_uint()

        self.if_inOctets = u.unpack_uhyper()
        self.if_inPackets = u.unpack_uint()
        self.if_inMcast = u.unpack_uint()
        self.if_inBcast = u.unpack_uint()
        self.if_inDiscard = u.unpack_uint()
        self.if_inError = u.unpack_uint()
        self.if_unknown = u.unpack_uint()

        self.if_outOctets = u.unpack_uhyper()
        self.if_outPackets = u.unpack_uint()
        self.if_outMcast = u.unpack_uint()
        self.if_outBcast = u.unpack_uint()
        self.if_outDiscard = u.unpack_uint()
        self.if_outError = u.unpack_uint()
 
        self.if_promisc = u.unpack_uint()

class EthernetCounters(object):
    def __init__(self, u):
        self.dot3StatsAlignmentErrors = u.unpack_uint()
        self.dot3StatsFCSErrors = u.unpack_uint()
        self.dot3StatsSingleCollisionFrames = u.unpack_uint()
        self.dot3StatsMultipleCollisionFrames = u.unpack_uint()
        self.dot3StatsSQETestErrors = u.unpack_uint()
        self.dot3StatsDeferredTransmissions = u.unpack_uint()
        self.dot3StatsLateCollisions = u.unpack_uint()
        self.dot3StatsExcessiveCollisions = u.unpack_uint()
        self.dot3StatsInternalMacTransmitErrors = u.unpack_uint()
        self.dot3StatsCarrierSenseErrors = u.unpack_uint()
        self.dot3StatsFrameTooLongs = u.unpack_uint()
        self.dot3StatsInternalMacReceiveErrors = u.unpack_uint()
        self.dot3StatsSymbolErrors = u.unpack_uint()

class VLANCounters(object):
    def __init__(self, u):
        self.vlan_id = u.unpack_uint()
        self.octets = u.unpack_uhyper()
        self.ucastPkts = u.unpack_uint()
        self.multicastPkts = u.unpack_uint()
        self.broadcastPkts = u.unpack_uint()
        self.discards = u.unpack_uint()

class TokenringCounters(object):
    def __init__(self, u):
        self.dot5StatsLineErrors = u.unpack_uint()
        self.dot5StatsBurstErrors = u.unpack_uint()
        self.dot5StatsACErrors = u.unpack_uint()
        self.dot5StatsAbortTransErrors = u.unpack_uint()
        self.dot5StatsInternalErrors = u.unpack_uint()
        self.dot5StatsLostFrameErrors = u.unpack_uint()
        self.dot5StatsReceiveCongestions = u.unpack_uint()
        self.dot5StatsFrameCopiedErrors = u.unpack_uint()
        self.dot5StatsTokenErrors = u.unpack_uint()
        self.dot5StatsSoftErrors = u.unpack_uint()
        self.dot5StatsHardErrors = u.unpack_uint()
        self.dot5StatsSignalLoss = u.unpack_uint()
        self.dot5StatsTransmitBeacons = u.unpack_uint()
        self.dot5StatsRecoverys = u.unpack_uint()
        self.dot5StatsLobeWires = u.unpack_uint()
        self.dot5StatsRemoves = u.unpack_uint()
        self.dot5StatsSingles = u.unpack_uint()
        self.dot5StatsFreqErrors = u.unpack_uint()

class VGCounters(object):
    def __init__(self, u):
        self.dot5StatsLineErrors = u.unpack_uint()
        self.dot5StatsBurstErrors = u.unpack_uint()
        self.dot5StatsACErrors = u.unpack_uint()
        self.dot5StatsAbortTransErrors = u.unpack_uint()
        self.dot5StatsInternalErrors = u.unpack_uint()
        self.dot5StatsLostFrameErrors = u.unpack_uint()
        self.dot5StatsReceiveCongestions = u.unpack_uint()
        self.dot5StatsFrameCopiedErrors = u.unpack_uint()
        self.dot5StatsTokenErrors = u.unpack_uint()
        self.dot5StatsSoftErrors = u.unpack_uint()
        self.dot5StatsHardErrors = u.unpack_uint()
        self.dot5StatsSignalLoss = u.unpack_uint()
        self.dot5StatsTransmitBeacons = u.unpack_uint()
        self.dot5StatsRecoverys = u.unpack_uint()
        self.dot5StatsLobeWires = u.unpack_uint()
        self.dot5StatsRemoves = u.unpack_uint()
        self.dot5StatsSingles = u.unpack_uint()
        self.dot5StatsFreqErrors = u.unpack_uint()

class HostCounters(object):
    format = 2000
    def __init__(self, u):
        self.hostname = u.unpack_string()
        self.uuid = u.unpack_fopaque(16)
        self.machine_type = u.unpack_uint()
        self.os_name = u.unpack_uint()
        self.os_release = u.unpack_string()

class HostAdapters(object):
    format = 2001
    def __init__(self, u):
        self.adapters = Struct("adapters",
            UBInt32("count"),
            Array(lambda c: c.count,
                Struct("adapter",
                    UBInt32("index"),
                    Bytes("MAC", 6)
                )
            )
        ).parse(u.get_buffer())

class HostParent(object):
    format = 2002
    def __init__(self, u):
        self.container_type = u.unpack_uint()
        self.container_index = u.unpack_uint()

class HostCPUCounters(object):
    format = 2003
    def __init__(self, u):
        self.load_one = u.unpack_float()
        self.load_five = u.unpack_float()
        self.load_fifteen = u.unpack_float()

        self.proc_run = u.unpack_uint()
        self.proc_total = u.unpack_uint()
        self.cpu_num = u.unpack_uint()
        self.cpu_speed = u.unpack_uint()
        self.uptime = u.unpack_uint()
        self.cpu_user = u.unpack_uint()
        self.cpu_nice = u.unpack_uint()
        self.cpu_system = u.unpack_uint()
        self.cpu_idle = u.unpack_uint()
        self.cpu_wio = u.unpack_uint()
        self.cpu_intr = u.unpack_uint()
        self.cpu_sintr = u.unpack_uint()
        self.interrupts = u.unpack_uint()
        self.contexts = u.unpack_uint()

class HostMemoryCounters(object):
    format = 2004
    def __init__(self, u):
        self.mem_total = u.unpack_uhyper()
        self.mem_free = u.unpack_uhyper()
        self.mem_shared = u.unpack_uhyper()
        self.mem_buffers = u.unpack_uhyper()
        self.mem_cached = u.unpack_uhyper()
        self.swap_total = u.unpack_uhyper()
        self.swap_free = u.unpack_uhyper()
        self.page_in = u.unpack_uint()
        self.page_out = u.unpack_uint()
        self.swap_in = u.unpack_uint()
        self.swap_out = u.unpack_uint()

class DiskIOCounters(object):
    format = 2005
    def __init__(self, u):
        self.disk_total = u.unpack_uhyper()
        self.disk_free = u.unpack_uhyper()
        self.part_max_used = u.unpack_uint()
        self.reads = u.unpack_uint()
        self.bytes_read = u.unpack_uhyper()
        self.read_time = u.unpack_uint()
        self.writes = u.unpack_uint()
        self.bytes_written = u.unpack_uhyper()
        self.write_time = u.unpack_uint()

class NetIOCounters(object):
    format = 2006
    def __init__(self, u):
        self.bytes_in = u.unpack_uhyper()
        self.pkts_in = u.unpack_uint()
        self.errs_in = u.unpack_uint()
        self.drops_in = u.unpack_uint()
        self.bytes_out = u.unpack_uhyper()
        self.packets_out = u.unpack_uint()
        self.errs_out = u.unpack_uint()
        self.drops_out = u.unpack_uint()

class SocketIPv4Counters(object):
    format = 2100
    def __init__(self, u):
        self.protocol = u.unpack_uint()
        self.local_ip = u.unpack_fstring(4)
        self.remote_ip = u.unpack_fstring(4)
        self.local_port = u.unpack_uint()
        self.remote_port = u.unpack_uint()

class SocketIPv6Counters(object):
    format = 2101
    def __init__(self, u):
        self.protocol = u.unpack_uint()
        self.local_ip = u.unpack_fstring(16)
        self.remote_ip = u.unpack_fstring(16)
        self.local_port = u.unpack_uint()
        self.remote_port = u.unpack_uint()

class VirtMemoryCounters(object):
    format = 2102
    def __init__(self, u):
        self.memory = u.unpack_uhyper()
        self.maxMemory = u.unpack_uhyper()

class VirtDiskIOCounters(object):
    format = 2103
    def __init__(self, u):
        self.capacity = u.unpack_uhyper()
        self.allocation = u.unpack_uhyper()
        self.available = u.unpack_uhyper()
        self.rd_req = u.unpack_uint()
        self.hyper = u.unpack_unsigend()
        self.wr_req = u.unpack_uint()
        self.wr_bytes = u.unpack_uhyper()
        self.errs = u.unpack_uint()

class VirtNetIOCounters(object):
    format = 2104
    def __init__(self, u):
        self.rx_bytes = u.unpack_uhyper()
        self.rx_packets = u.unpack_uint()
        self.rx_errs = u.unpack_uint()
        self.rx_drop = u.unpack_uint()
        self.tx_bytes = u.unpack_uhyper()
        self.tx_packets = u.unpack_uint()
        self.tx_errs = u.unpack_uint()
        self.tx_drop = u.unpack_uint()

def getDecoder(format):
    decoders = {
        1: InterfaceCounters,
        2: EthernetCounters,
        3: TokenringCounters,
        4: VGCounters,
        5: VLANCounters,
        2000: HostCounters,
        2001: HostAdapters,
        2002: HostParent,
        2003: HostCPUCounters,
        2004: HostMemoryCounters,
        2005: DiskIOCounters,
        2006: NetIOCounters,
        2101: SocketIPv6Counters,
        2102: VirtMemoryCounters,
        2103: VirtDiskIOCounters,
        2104: VirtNetIOCounters
    }

    return decoders.get(format, None)

