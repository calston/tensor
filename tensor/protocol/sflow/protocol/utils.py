import struct, socket


def unpack_address(u):
    addrtype = u.unpack_uint()

    if self.addrtype == 1:
        self.address = u.unpack_fopaque(4)

    if self.addrtype == 2:
        self.address = u.unpack_fopaque(16)
    
    return self.address

class IPv4Address(object):
    def __init__(self, addr_int):
        self.addr_int = addr_int
        self.na = struct.pack('!L', addr_int)
    
    def __str__(self):
        return socket.inet_ntoa(self.na)

    def asString(self):
        return str(self)

    def __repr__(self):
        return "<IPv4Address ip=\"%s\">" % str(self)
