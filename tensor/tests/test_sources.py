from twisted.trial import unittest
from twisted.internet import defer

from tensor.sources.linux import basic, process

class Tests(unittest.TestCase):
    def _qb(self, result):
        pass

    def test_linux_cpu(self):
        s = basic.CPU({'interval': 1.0, 'service': 'cpu', 'ttl': 60}, self._qb, None)

        try:
            e = s.get()
            e = s.get()
        except:
            raise unittest.SkipTest('Might not exist in docker')

    def test_linux_memory(self):
        s = basic.Memory({'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        s.get()

    def test_linux_load(self):
        s = basic.LoadAverage({'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        s.get()

    @defer.inlineCallbacks
    def test_process_count(self):
        s = process.ProcessCount({'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        r = yield s.get()

    @defer.inlineCallbacks
    def test_disk_space(self):
        s = basic.DiskFree({'interval': 1.0, 'service': 'df', 'ttl': 60}, self._qb, None)

        r = yield s.get()

