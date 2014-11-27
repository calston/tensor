import json
import socket

from twisted.trial import unittest
from twisted.internet import defer, endpoints, reactor
from twisted.web import server, static

from tensor.sources.linux import basic, process
from tensor.sources import riak


class TestLinuxSources(unittest.TestCase):
    def skip_if_no_hostname(self):
        try:
            socket.gethostbyaddr(socket.gethostname())
        except socket.herror:
            raise unittest.SkipTest('Unable to get local hostname.')

    def _qb(self, result):
        pass

    def test_basic_cpu(self):
        self.skip_if_no_hostname()
        s = basic.CPU(
            {'interval': 1.0, 'service': 'cpu', 'ttl': 60}, self._qb, None)

        try:
            s.get()
            s.get()
        except:
            raise unittest.SkipTest('Might not exist in docker')

    def test_basic_cpu_calculation(self):
        s = basic.CPU({
            'interval': 1.0,
            'service': 'cpu',
            'ttl': 60,
            'hostname': 'localhost',
        }, self._qb, None)

        stats = "cpu  2255 34 2290 25563 6290 127 456 0 0 0"
        s._read_proc_stat = lambda: stats
        # This is the first time we're getting this stat, so we return zeros
        [cpu_event, iowait_event] = s.get()
        self.assertEqual(cpu_event.service, 'cpu')
        self.assertEqual(round(cpu_event.metric, 4), 0.0)
        self.assertEqual(iowait_event.service, 'cpu.iowait')
        self.assertEqual(round(iowait_event.metric, 4), 0.0)

        stats = "cpu  4510 68 4580 51126 12580 254 912 0 0 0"
        s._read_proc_stat = lambda: stats
        [cpu_event, iowait_event] = s.get()
        self.assertEqual(cpu_event.service, 'cpu')
        self.assertEqual(round(cpu_event.metric, 4), 0.1395)
        self.assertEqual(iowait_event.service, 'cpu.iowait')
        self.assertEqual(round(iowait_event.metric, 4), 0.1699)

    def test_basic_memory(self):
        self.skip_if_no_hostname()
        s = basic.Memory(
            {'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        s.get()

    def test_basic_load(self):
        self.skip_if_no_hostname()
        s = basic.LoadAverage(
            {'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        s.get()

    @defer.inlineCallbacks
    def test_process_count(self):
        self.skip_if_no_hostname()
        s = process.ProcessCount(
            {'interval': 1.0, 'service': 'mem', 'ttl': 60}, self._qb, None)

        yield s.get()

    @defer.inlineCallbacks
    def test_basic_disk_space(self):
        self.skip_if_no_hostname()
        s = basic.DiskFree(
            {'interval': 1.0, 'service': 'df', 'ttl': 60}, self._qb, None)

        yield s.get()

    @defer.inlineCallbacks
    def test_process_stats(self):
        self.skip_if_no_hostname()
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
