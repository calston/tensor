from twisted.trial import unittest
from twisted.internet import defer

from tensor.sources.linux import basic, process

class Tests(unittest.TestCase):
    def test_linux_cpu(self):
        def qb(_):
            print _
        s = basic.CPU({'interval': 1.0, 'service': 'cpu', 'ttl': 60}, qb)

        e = s.get()
        e = s.get()

    def test_linux_memory(self):
        def qb(_):
            print _
        s = basic.Memory({'interval': 1.0, 'service': 'mem', 'ttl': 60}, qb)

        s.get()

    def test_linux_load(self):
        def qb(_):
            print _
        s = basic.LoadAverage({'interval': 1.0, 'service': 'mem', 'ttl': 60}, qb)

        s.get()

    @defer.inlineCallbacks
    def test_process_count(self):
        def qb(_):
            print _
        s = process.ProcessCount({'interval': 1.0, 'service': 'mem', 'ttl': 60}, qb)

        r = yield s.get()

    @defer.inlineCallbacks
    def test_disk_space(self):
        def qb(_):
            print _

        s = basic.DiskFree({'interval': 1.0, 'service': 'df', 'ttl': 60}, qb)

        r = yield s.get()

