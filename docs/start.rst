Getting started
***************

Installation
============

Tensor can be installed from PyPi with pip ::

    $ pip install tensor

This will also install Twisted, protobuf and PyYAML

Or you can use the .deb package. Let the latest release from https://github.com/calston/tensor/releases/latest ::
    
    $ aptitude install python-twisted python-protobuf python-yaml
    $ wget https://github.com/calston/tensor/releases/download/0.3.0/tensor_0.3.0_amd64.deb
    $ dpkg -i tensor_0.3.0_amd64.deb

This also gives you an init script and default config in /etc/tensor/

Creating a configuration file
=============================

Tensor uses a simple YAML configuration file

The first basic requirements are the Riemann server and port (defaults to
localhost:5555) and the queue interval::

    server: localhost
    port: 5555
    interval: 1.0
    proto: udp

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

Using outputs
=============
You can configure multiple outputs which receive a copy of every message
for example ::

    outputs:
        - output: tensor.outputs.riemann.RiemannTCP
          server: localhost
          port: 5555

If you enable multiple outputs then the `server`, `port` and `proto` options
will go un-used and the default Riemann TCP transport won't start.

You can configure as many outputs as you like, or create your own.

Using sources
=============

To configure the basic CPU usage source add it to the `sources` list in the
config file ::

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
        googledns.latency: "> 100",
        googledns.loss: "> 0"
    }

This will ping `8.8.8.8` every 60 seconds and raise a critical alert for
the latency metric if it exceeds 100ms, and the packet loss metric if there
is any at all.

Configuration
=============
Sources can contain any number of configuration attributes which vary between
them. All sources take the following options though

+--------------+-----------+-------------------------------------------------+
| service      | mandatory | Service name after which extra metric names are |
|              |           | appended, dot separated                         |
+--------------+-----------+-------------------------------------------------+
| interval     | depends   | Clock tick interval, for sources which implement|
|              |           | a polling clock                                 |
+--------------+-----------+-------------------------------------------------+
| ttl          | optional  | TTL for metric expiry in Riemann                |
+--------------+-----------+-------------------------------------------------+
| hostname     | optional  | Hostname to tag this service with. Defaults to  |
|              |           | system FQDN but can be overriden.               |
+--------------+-----------+-------------------------------------------------+
| tags         | optional  | Comma separated list of tags for metrics        |
+--------------+-----------+-------------------------------------------------+

State triggers
==============

`critical` and `warning` matches can also be a regular expression for sources
which output keys for different devices and metrics::

    service: network
    source: tensor.sources.linux.basic.Network
    ...
    critical: {
        network.\w+.tx_packets: "> 1000",
    }

Routing sources
===============

Since multiple outputs can be added, Tensor events can be routed from sources
to specific outputs or multiple outputs. By default events are routed to all
outputs.

To enable routing, outputs need a unique `name` attribute::

    outputs:
        - output: tensor.outputs.riemann.RiemannTCP
          name: riemann1
          server: riemann1.acme.com
          port: 5555

        - output: tensor.outputs.riemann.RiemannTCP
          name: riemann2
          server: riemann2.acme.com
          port: 5555

        - output: tensor.outputs.riemann.RiemannUDP
          name: riemannudp
          server: riemann1.acme.com
          port: 5555

    sources:
        - service: cpu1
          source: tensor.sources.linux.basic.CPU
          interval: 1.0
          route: riemannudp

        - service: cpu2
          source: tensor.sources.linux.basic.CPU
          interval: 1.0
          route:
            - riemann1
            - riemann2

The `route` attribute can also accept a list of output names. The above
configuration would route cpu1 metrics to the UDP output, and the cpu2
metrics to both riemann1 and riemann2 TCP outputs.

Starting Tensor
===============

To start Tensor, simply use twistd to run the service and pass a config file::

    twistd -n tensor -c tensor.yml

If you're using the Debian package then an init script is included.
