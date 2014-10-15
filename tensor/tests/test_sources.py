from twisted.trial import unittest

from tensor.sources.linux import basic

class Tests(unittest.TestCase):
    def test_linux_cpu(self):
        def qb(_):
            print _
        s = basic.CPU({'interval': 1.0, 'service': 'cpu'}, qb)

        e = s.get()
        e = s.get()

    def test_linux_memory(self):
        def qb(_):
            print _
        s = basic.Memory({'interval': 1.0, 'service': 'mem'}, qb)

        s.get()
