from twisted.trial import unittest

from twisted.internet import defer, reactor, error

from tensor import utils

class Tests(unittest.TestCase):
    def test_persistent_cache(self):
        pc = utils.PersistentCache(location='test.cache')

        pc.set('foo', 'bar')
        pc.set('bar', 'baz')

        pc2 = utils.PersistentCache(location='test.cache')

        self.assertEquals(pc2.get('foo')[1], 'bar')

        pc.set('foo', 'baz')

        self.assertEquals(pc2.get('foo')[1], 'baz')

        pc.delete('foo')

        self.assertFalse(pc.contains('foo'))
        self.assertTrue(pc.contains('bar'))

        pc.expire(0)

        self.assertFalse(pc.contains('bar'))

