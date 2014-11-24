import json
import socket

from twisted.trial import unittest
from twisted.internet import defer, endpoints, reactor
from twisted.web import server, static

from tensor.sources.linux import basic, process
from tensor.sources import riak


class TestLinuxSources(unittest.TestCase):
    def setUp(self):
        try:
            socket.gethostbyaddr(socket.gethostname())
        except socket.herror:
            raise unittest.SkipTest('Unable to get local hostname.')

    def _qb(self, result):
        pass

    def test_basic_cpu(self):
        s = basic.CPU(
            {'interval': 1.0, 'service': 'cpu', 'ttl': 60}, self._qb, None)

        try:
            s.get()
            s.get()
        except:
            raise unittest.SkipTest('Might not exist in docker')

    def test_basic_memory(self):
        s = basic.Memory(
            {'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        s.get()

    def test_basic_load(self):
        s = basic.LoadAverage(
            {'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        s.get()

    @defer.inlineCallbacks
    def test_process_count(self):
        s = process.ProcessCount(
            {'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        yield s.get()

    @defer.inlineCallbacks
    def test_basic_disk_space(self):
        s = basic.DiskFree(
            {'interval': 1.0, 'service': 'df', 'ttl': 60}, self._qb, None)

        yield s.get()

    @defer.inlineCallbacks
    def test_process_stats(self):
        s = process.ProcessStats(
            {'interval': 1.0, 'service': 'ps', 'ttl': 60}, self._qb, None)

        yield s.get()


class TestRiakSources(unittest.TestCase):
    def _qb(self, result):
        pass

    def start_fake_riak_server(self, stats):
        def cb(listener):
            self.addCleanup(listener.stopListening)
            return listener

        data = static.Data(json.dumps(stats), 'application/json')
        data.isLeaf = True
        site = server.Site(data)
        endpoint = endpoints.TCP4ServerEndpoint(reactor, 0)
        return endpoint.listen(site).addCallback(cb)

    def make_riak_stats_source(self, config_overrides={}):
        config = {
            'interval': 1.0,
            'service': 'riak',
            'ttl': 60,
            'hostname': 'localhost',
        }
        config.update(config_overrides)
        return riak.RiakStats(config, self._qb, None)

    @defer.inlineCallbacks
    def test_riak_stats_zeros(self):
        listener = yield self.start_fake_riak_server({
            'node_gets': 0,
            'node_puts': 0,
        })
        addr = listener.getHost()
        url = 'http://localhost:%s/' % (addr.port,)
        s = self.make_riak_stats_source({'url': url})

        [gets, puts] = yield s.get()
        self.assertEqual(gets.service, "riak.gets_per_second")
        self.assertEqual(gets.metric, 0.0)
        self.assertEqual(puts.service, "riak.puts_per_second")
        self.assertEqual(puts.metric, 0.0)

    @defer.inlineCallbacks
    def test_riak_stats(self):
        listener = yield self.start_fake_riak_server({
            'node_gets': 150,
            'node_puts': 45,
        })
        addr = listener.getHost()
        url = 'http://localhost:%s/' % (addr.port,)
        s = self.make_riak_stats_source({'url': url})

        [gets, puts] = yield s.get()
        self.assertEqual(gets.service, "riak.gets_per_second")
        self.assertEqual(gets.metric, 2.5)
        self.assertEqual(puts.service, "riak.puts_per_second")
        self.assertEqual(puts.metric, 0.75)
