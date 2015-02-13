from zope.interface import implements

from twisted.internet import defer

from tensor.interfaces import ITensorSource
from tensor.objects import Source
from tensor.utils import fork

class ProcessCount(Source):
    """Returns the ps count on the system

    **Metrics:**

    :(service name): Number of processes
    """
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        out, err, code = yield fork('/bin/ps', args=('-e',))

        count = len(out.strip('\n').split('\n')) - 1

        defer.returnValue(
            self.createEvent('ok', 'Process count %s' % (count), count)
        )

class ProcessStats(Source):
    """Returns memory used by each active parent process

    **Metrics:**

    :(service name).proc.(process name).cpu: Per process CPU usage
    :(service name).proc.(process name).memory: Per process memory use
    :(service name).proc.(process name).age: Per process age
    :(service name).user.(user name).cpu: Per user CPU usage
    :(service name).user.(user name).memory: Per user memory use
    """
    implements(ITensorSource)

    @defer.inlineCallbacks
    def get(self):
        out, err, code = yield fork('/bin/ps', args=(
            '-eo','pid,user,etime,rss,pcpu,comm,cmd'))

        lines = out.strip('\n').split('\n')

        cols = lines[0].split()

        procs = {}
        users = {}

        vals = []

        for l in lines[1:]:
            parts = l.split(None, len(cols) - 1)

            proc = {}
            for i, e in enumerate(parts):
                proc[cols[i]] = e.strip()

            parts = None

            elapsed = proc['ELAPSED']
            if '-' in elapsed:
                days = int(elapsed.split('-')[0])
                hours, minutes, seconds = [
                    int (i) for i in elapsed.split('-')[1].split(':')]
                age = (days*24*60*60) + (hours*60*60) + (minutes*60)
                age += seconds

            elif elapsed.count(':')==2:
                hours, minutes, seconds = [
                    int (i) for i in elapsed.split(':')]
                age = (hours*60*60) + (minutes*60) + seconds

            else:
                minutes, seconds = [
                    int (i) for i in elapsed.split(':')]
                age = (minutes*60) + seconds

            # Ignore kernel and tasks that just started, usually it's this ps
            if (proc['CMD'][0] != '[') and (age>0):
                binary = proc['CMD'].split()[0].split('/')[-1].strip(':').strip('-')
                pid = proc['PID']
                cmd = proc['CMD']
                comm = proc['COMMAND']
                user = proc['USER']

                mem = int(proc['RSS'])/1024.0
                cpu = float(proc['%CPU'])

                if user in users:
                    users[user]['cpu'] += cpu
                    users[user]['mem'] += mem
                else:
                    users[user] = {
                        'cpu': cpu, 'mem': mem
                    }

                if binary != comm:
                    key = "%s.%s" % (binary,comm)
                else:
                    key = comm

                key = key.strip('.')

                if key in procs:
                    procs[key]['cpu'] += cpu
                    procs[key]['mem'] += mem
                    procs[key]['age'] += age
                else:
                    procs[key] = {
                        'cpu': cpu, 'mem': mem, 'age': age
                    }

        events = []

        for k,v in users.items():
            events.append(self.createEvent('ok', 'User memory %s: %0.2fMB' % (
                k, v['mem']), v['mem'], prefix="user.%s.mem" % k))
            events.append(self.createEvent('ok', 'User CPU usage %s: %s%%' % (
                k, int(v['cpu']*100)), v['cpu'], prefix="user.%s.cpu" % k))

        for k,v in procs.items():
            events.append(self.createEvent('ok', 'Process age %s: %ss' % (
                k, v['age']), v['age'], prefix="proc.%s.age" % k))
            events.append(self.createEvent('ok', 'Process memory %s: %0.2fMB' % (
                k, v['mem']), v['mem'], prefix="proc.%s.mem" % k))
            events.append(
                self.createEvent('ok', 'Process CPU usage %s: %s%%' % (
                    k, int(v['cpu']*100)), v['cpu'],
                    prefix="proc.%s.cpu" % k
                )
            )

        defer.returnValue(events)
