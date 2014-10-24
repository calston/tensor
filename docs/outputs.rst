Outputs
*******

Introduction
============

Outputs are Python objects which subclass :class:`tensor.objects.Output`. They
are constructed with a dictionary parsed from the YAML configuration block
which defines them, and as such can read any attributes from that either
optional or mandatory.

Since outputs are constructed at startup time they can retain any required
state. A copy of the queue is passed to all 
:method:`tensor.objects.Output.eventsReceived` calls which happen at each 
queue `interval` config setting as the queue is emptied. This list of
:class:`tensor.objects.Event` objects must not be altered by the output.

The `output` configuration option is passed a string representing an object
the same way as `sources` configurations are ::

    output: tensor.sources.network.Ping


Writing your own outputs
========================

An output clas should subclass :class:`tensor.objects.Output`.

The output can implement a `createClient` method which starts the output in
whatever way necessary and can be a deferred. The output must also have a
`eventsReceived` method which takes a list of :class:`tensor.objects.Event`
objects and process them accordingly, it can also be a deferred.

An example logging source::

    from twisted.internet import reactor, defer
    from twisted.python import log

    from tensor.objects import Output

    class Logger(Output):
        def eventsReceived(self, events):
            log.msg("Events dequeued: %s" % len(events))

If you save this as `test.py` the basic configuration you need is simply ::

    outputs:
        - output: tensor.outputs.riemann.RiemannUDP
          server: localhost
          port: 5555

        - output: test.Logger

You should now see how many events are exiting in the Tensor log file ::

    2014-10-24 15:35:27+0200 [-] Starting protocol <tensor.protocol.riemann.RiemannUDP object at 0x7f3b5ae15810>
    2014-10-24 15:35:28+0200 [-] Events dequeued: 7
    2014-10-24 15:35:29+0200 [-] Events dequeued: 2
    2014-10-24 15:35:30+0200 [-] Events dequeued: 3

