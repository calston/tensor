from twisted.trial import unittest

from tensor.logs import follower, parsers

import datetime
import os


class TestLogs(unittest.TestCase):
 
    def test_logfollow(self):
        try:
            os.unlink('test.log.lf')
            os.unlink('test.log')
        except:
            pass

        log = open('test.log', 'wt')
        log.write('foo\nbar\n')
        log.flush()

        f = follower.LogFollower('test.log', tmp_path=".", history=True)

        r = f.get()

        log.write('test')
        log.flush()

        r2 = f.get()

        log.write('ing\n')
        log.flush()

        r3 = f.get()

        self.assertEqual(r[0], 'foo')
        self.assertEqual(r[1], 'bar')

        self.assertEqual(r2, [])
        self.assertEqual(r3[0], 'testing')

        log.close()

        # Move inode
        os.rename('test.log', 'testold.log')

        log = open('test.log', 'wt')
        log.write('foo2\nbar2\n')
        log.close()

        r = f.get()

        self.assertEqual(r[0], 'foo2')
        self.assertEqual(r[1], 'bar2')

        # Go backwards
        log = open('test.log', 'wt')
        log.write('foo3\n')
        log.close()

        r = f.get()

        self.assertEqual(r[0], 'foo3')

        os.unlink('test.log')
        os.unlink('testold.log')

    def test_apache_parser(self):
        log = parsers.ApacheLogParser('combined')

        line = '192.168.0.102 - - [16/Jan/2015:11:11:45 +0200] "GET / HTTP/1.1" 200 709 "-" "My browser"'

        want = {
            'status': 200, 
            'request': 'GET / HTTP/1.1', 
            'bytes': 709, 
            'user-agent': 'My browser', 
            'client': '192.168.0.102', 
            'time': datetime.datetime(2015, 1, 16, 11, 11, 45),
            'referer': None,
            'logname': None, 
            'user': None,
        }
    
        p = log.parse(line)

        for k,v in want.items():
            self.assertEquals(p[k], v)
