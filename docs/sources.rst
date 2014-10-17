Sources
*******

Introduction
============

Sources are Python objects which subclass :class:`tensor.objects.Source`. They
are constructed with a dictionary parsed from the YAML configuration block
which defines them, and as such can read any attributes from that either
optional or mandatory.

Since sources are constructed at startup time they can retain any required
state, for example the last metric value to report rates of change or for
any other purpose. However since a Tensor process might be running many checks
a source should not use an excessive amount of memory.

The `source` configuration option is passed a string representing an object
in much the same way as you would import it in a python module. The final
class name is split from this string. For example specifying::

    source: tensor.sources.network.Ping

is equivalent to::

    from tensor.sources.network import Ping

Writing your own sources
========================

A source class must subclass :class:`tensor.objects.Source` and also
implement the interface :class:`tensor.interfaces.ITensorSource`

The source must have a `get` method which returns a :class:`tensor.objects.Event`
object. The Source parent class provides a helper method `createEvent` which
performs the metric level checking (evaluating the simple logical statement in
the configuration), sets the correct service name and handles prefixing service
names.

A "Hello world" source::

    from zope.interface import implements

    from tensor.interfaces import ITensorSource
    from tensor.objects import Source

    class HelloWorld(Source):
        implements(ITensorSource)
        
        def get(self):
            return self.createEvent('ok', 'Hello world!', 0)

To hold some state, you can re-implement the `__init__` method, as long as the
arguments remain the same.

Extending the above example to create a simple flip-flop metric event::

    from zope.interface import implements

    from tensor.interfaces import ITensorSource
    from tensor.objects import Source

    class HelloWorld(Source):
        implements(ITensorSource)

        def __init__(self, config, qb):
            Source.__init__(self, config, qb)
            self.bit = False

        def get(self):
            self.bit = not self.bit
            return self.createEvent('ok', 'Hello world!', self.bit and 0.0 or 1.0)

You could then place this in a Python module like `hello.py` and as long as it's
in the Python path for Tensor it can be used as a source with `hello.HelloWorld`

Handling asynchronous tasks
===========================

Since Tensor is written using the Twisted asynchronous framework, sources can
(and in most cases *must*) make full use of it to implement network checks, or
execute other processes.

The simplest example of a source which executes an external process is the
ProcessCount check::

    from zope.interface import implements

    from twisted.internet import defer, utils

    from tensor.interfaces import ITensorSource
    from tensor.objects import Source

    class ProcessCount(Source):
        implements(ITensorSource)

        @defer.inlineCallbacks
        def get(self):
            out, err, code = yield utils.getProcessOutputAndValue('/bin/ps',
                args=('-e',))

            count = len(out.strip('\n').split('\n'))

            defer.returnValue(
                self.createEvent('ok', 'Process count %s' % (count), count)
            )

For more information please read the Twisted documentation at https://twistedmatrix.com/trac/wiki/Documentation

It's also interesting to note that, there is nothing stopping you from starting
listening services within a source which processes and relays events to Riemann
implementing some protocol.
