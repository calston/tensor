Getting started
***************

Installation
============

Tensor can be installed with from PyPi with pip::

    pip install tensor

This will also install Twisted, protobuf and PyYAML

Creating a configuration file
=============================

Tensor uses a simple YAML configuration file

The first basic requirements are the Riemann server and port (defaults to
localhost:5555) and the queue interval::

    server: localhost
    port: 5555
    interval: 1.0

Tensors checks are Python classes (called sources) which are instantiated
with the configuration block which defines them. Rather than being one-shot
scripts, a source object remains in memory with its own timer which adds
events to a queue. The `interval` defined above is the rate at which these
events are rolled up into a message and sent to Riemann.

It is important then that `interval` is set to a value appropriate to how
frequently you want to see them in Riemann, as well as the rate at which
they collect metrics from the system. All `interval` attributes are floating
point in seconds, this means you can check (and send to Riemann) at rates
well below 1 second.

To configure the basic CPU usage source add it to the `sources` list in the
config file::

    sources:
        - service: cpu
          source: tensor.sources.linux.basic.CPU
          interval: 1.0
          warning: {
            cpu: "> 0.5"
          }
          critical: {
            cpu: "> 0.8"
          }

This will measure the CPU from /proc/stat every second, with a warning state
if the value exceeds 50%, and a critical state if it exceeds 80%

The `service` attribute can be any string you like, populating the `service`
field in Riemann. The logical expression to raise the state of the event
is (eg. critical) is assigned to a key which matches the service name.

Sources may return more than one metric, in which case it will add a prefix
to the service. The state expression must correspond to that as well.

For example, the Ping check returns both latency and packet loss::

    service: googledns
    source: tensor.sources.network.Ping
    interval: 60.0
    destination: 8.8.8.8
    critical: {
        googledns_latency: "> 100",
        googledns_loss: "> 0"
    }

This will ping `8.8.8.8` every 60 seconds and raise a critical alert for
the latency metric if it exceeds 100ms, and the packet loss metric if there
is any at all.

Starting Tensor
===============

To start Tensor, simply use twistd to run the service and pass a config file::

    twistd -n tensor -c tensor.yml
