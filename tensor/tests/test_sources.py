import json
import socket

from twisted.trial import unittest
from twisted.internet import defer, endpoints, reactor
from twisted.web import server, static

from tensor.sources.linux import basic, process
from tensor.sources import riak, nginx, network

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
        # This is the first time we're getting this stat, so we get no events.
        self.assertEqual(s.get(), None)

        stats = "cpu  4510 68 4580 51126 12580 254 912 0 0 0"
        s._read_proc_stat = lambda: stats
        events = s.get()
        cpu_event = events[-1]
        iowait_event = events[4]
        self.assertEqual(cpu_event.service, 'cpu')
        self.assertEqual(round(cpu_event.metric, 4), 0.1395)
        self.assertEqual(iowait_event.service, 'cpu.iowait')
        self.assertEqual(round(iowait_event.metric, 4), 0.1699)

    def test_basic_cpu_calculation_no_guest_stats(self):
        s = basic.CPU({
            'interval': 1.0,
            'service': 'cpu',
            'ttl': 60,
            'hostname': 'localhost',
        }, self._qb, None)

        stats = "cpu  2255 34 2290 25563 6290 127 456 0"
        s._read_proc_stat = lambda: stats
        # This is the first time we're getting this stat, so we get no events.
        self.assertEqual(s.get(), None)

        stats = "cpu  4510 68 4580 51126 12580 254 912 0"
        s._read_proc_stat = lambda: stats
        events = s.get()
        cpu_event = events[-1]
        iowait_event = events[4]
        self.assertEqual(cpu_event.service, 'cpu')
        self.assertEqual(round(cpu_event.metric, 4), 0.1395)
        self.assertEqual(iowait_event.service, 'cpu.iowait')
        self.assertEqual(round(iowait_event.metric, 4), 0.1699)

    def test_disk_io(self):
        s = basic.DiskIO({
            'interval': 1.0,
            'service': 'disk',
            'ttl': 60,
            'hostname': 'localhost'}, self._qb, None)

        stats = [
            '   1       0 ram0 0 0 0 0 0 0 0 0 0 0 0',
            '   7       0 loop0 0 0 0 0 0 0 0 0 0 0 0',
            ' 202       2 xvda2 2 0 4 64 0 0 0 0 0 64 64',
            ' 202      32 xvdc 576 10 3739 748 144 0 4497 18080 0 8616 18828',
            ' 202      33 xvdc1 423 0 2435 264 144 0 4497 18080 0 8132 18344',
        ]

        s._getstats = lambda: stats
        events = s.get()

        self.assertEqual(events[0].metric, 32)
        self.assertEqual(events[1].metric, 2)

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

    @defer.inlineCallbacks
    def test_http_request(self):
        self.skip_if_no_hostname()
        s = network.HTTP({
            'interval': 1.0, 
            'service': 'http', 
            'ttl': 60,
            'url': 'http://imcol.in/'
        }, self._qb, None)

        event = yield s._get()
        self.assertEquals(event.state, 'ok')

    @defer.inlineCallbacks
    def test_http_request_timeout(self):
        self.skip_if_no_hostname()
        s = network.HTTP({
            'interval': 1.0, 
            'service': 'http', 
            'ttl': 60,
            'timeout': 1,
            'url': 'http://1.1.1.1/'
        }, self._qb, None)

        event = yield s._get()
        self.assertEquals(event.state, 'critical')
        self.assertEquals('timeout' in event.description, True)

    @defer.inlineCallbacks
    def test_http_request_fail(self):
        self.skip_if_no_hostname()
        s = network.HTTP({
            'interval': 1.0, 
            'service': 'http', 
            'ttl': 60,
            'url': 'http://noresolve/'
        }, self._qb, None)

        event = yield s._get()
        self.assertEquals(event.state, 'critical')

    def test_network_stats(self):
        self.skip_if_no_hostname()
        s = basic.Network(
            {'interval': 1.0, 'service': 'net', 'ttl': 60}, self._qb, None)

        s._readStats = lambda: [
            '  eth0: 254519754 1437339    0    0    0     0          0      '+
            '   0 202067280 1154168    0    0    0     0       0          0',
            '    lo: 63830682  900933    0    0    0     0          0       '+
            '  0 63830682  900933    0    0    0     0       0          0'
        ]

        ev = s.get()
        self.assertEquals(ev[0].metric, 254519754)
        self.assertEquals(ev[1].metric, 1437339)
        self.assertEquals(ev[2].metric, 0)
        self.assertEquals(ev[3].metric, 202067280)
        self.assertEquals(ev[4].metric, 1154168)
        self.assertEquals(ev[5].metric, 0)

    def test_nginx_parse(self):
        src = nginx.Nginx({
            'interval': 1.0, 
            'service': 'nginx', 
            'ttl': 60, 
            'hostname': 'localhost',
            'stats_url': 'http://localhost/nginx_stats'
        }, self._qb, None)

        ngstats = """Active connections: 3
server accepts handled requests
 20649 20649 686969
Reading: 0 Writing: 1 Waiting: 2\n"""

        metrics = src._parse_nginx_stats(ngstats)

        self.assertEquals(metrics['handled'][0], 20649)

    def test_nginx_log_nohistory(self):
        try:
            os.unlink('foo.log.lf')
            os.unlink('foo.log')
        except:
            pass

        events = []

        def qb(src, ev):
            events.append(ev)

        f = open('foo.log', 'wt')
        f.write('192.168.0.1 - - [16/Jan/2015:16:31:29 +0200] "GET /foo HTTP/1.1" 200 210 "-" "My Browser"\n')
        f.write('192.168.0.1 - - [16/Jan/2015:16:51:29 +0200] "GET /foo HTTP/1.1" 200 410 "-" "My Browser"\n')
        f.flush()

        src = nginx.NginxLogMetrics({
            'interval': 1.0,
            'service': 'nginx',
            'ttl': 60,
            'hostname': 'localhost',
            'log_format': 'combined',
            'file': 'foo.log'
        }, qb, None)

        src.log.tmp = 'foo.log2.lf'

        src.get()

        self.assertEquals(len(events), 0)

        f.write('192.168.0.1 - - [16/Jan/2015:17:31:29 +0200] "GET /foo HTTP/1.1" 200 210 "-" "My Browser"\n')
        f.write('192.168.0.1 - - [16/Jan/2015:17:51:29 +0200] "GET /foo HTTP/1.1" 200 410 "-" "My Browser"\n')
        f.flush()

        src.get()

        self.assertEquals(len(events)>0, True)

    def test_nginx_log(self):
        try:
            os.unlink('foo.log.lf')
            os.unlink('foo.log')
        except:
            pass

        events = []

        def qb(src, ev):
            events.append(ev)

        f = open('foo.log', 'wt')
        f.write('192.168.0.1 - - [16/Jan/2015:16:31:29 +0200] "GET /foo HTTP/1.1" 200 210 "-" "My Browser"\n')
        f.write('192.168.0.1 - - [16/Jan/2015:16:51:29 +0200] "GET /foo HTTP/1.1" 200 410 "-" "My Browser"\n')
        f.flush()

        src = nginx.NginxLogMetrics({
            'interval': 1.0,
            'service': 'nginx',
            'ttl': 60,
            'hostname': 'localhost',
            'log_format': 'combined',
            'history': True,
            'file': 'foo.log'
        }, qb, None)

        src.log.tmp = 'foo.log.lf'

        src.get()

        ev1 = events[0]
        ev2 = events[1]

        for i in ev1:
            if i.service=='nginx.client.192.168.0.1.bytes':
                self.assertEquals(i.metric, 210)

        for i in ev2:
            if i.service=='nginx.client.192.168.0.1.bytes':
                self.assertEquals(i.metric, 410)

        events = []

        f.write('192.168.0.1 - - [16/Jan/2015:17:10:31 +0200] "GET /foo HTTP/1.1" 200 410 "-" "My Browser"\n')
        f.write('192.168.0.1 - - [16/Jan/2015:17:10:34 +0200] "GET /bar HTTP/1.1" 200 410 "-" "My Browser"\n')
        f.close()

        src.get()

        for i in events[0]:
            if i.service=='nginx.client.192.168.0.1.requests':
                self.assertEquals(i.metric, 2)
            if i.service=='nginx.user-agent.My Browser.bytes':
                self.assertEquals(i.metric, 820)

            if i.service=='nginx.request./foo.bytes':
                self.assertEquals(i.metric, 410)

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
