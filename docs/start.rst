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

Some first basic requirements are the Riemann server and port (defaults to
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

Riemann is the default output in this configuration, but there are others.

Using outputs
=============

A better and more explicit means of configuring where events go is to use
the `output` framework. Currently there is support for Elasticsearch and
Riemann, but this can easily be extended.

You can configure multiple outputs which receive a copy of every message
for example ::

    outputs:
        - output: tensor.outputs.riemann.RiemannTCP
          server: localhost
          port: 5555

If you enable multiple outputs then the global `server`, `port` and `proto`
options will go un-used and the default Riemann TCP transport won't start.

You can configure as many outputs as you like, or create your own.

Using Elasticsearch instead
===========================

You may wish to output events directly into Elasticsearch in which case
your configuration would look like this ::

    outputs:
        - output: tensor.outputs.elasticsearch.ElasticSearch
          server: 127.0.0.1
          port: 9200

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

Remote SSH checks
=================

A new feature in Tensor is the ability to perform checks on a remote device
using SSH. This is currently only supported by certain sources. 

To perform a check over SSH we need an `ssh_host` which defaults to the check
hostname, `ssh_username`, and one of `ssh_key`, `ssh_keyfile` or `ssh_password`.
All of these except the ssh_host parameter can be specified globally and/or
on a specific source to override the global configuration.

`ssh_key` allows providing a private key in a YAML text blob. If `ssh_key` or 
`ssh_keyfile` is password encrypted then `ssh_keypass` can be set to that in
plain text - although this isn't really recommendable.

Example ::

    ssh_username: tensor
    ssh_key: |
        Proc-Type: 4,ENCRYPTED
        DEK-Info: AES-128-CBC,A6588464A721D661311DBCE44C76337E

        /bqr0AEIbiWubFiPEcdlNw8WdDrFqELOCZo78ohtDX/2HJhkMCCtAuv46is5UCvj
        pweYupJQgZZ9g+6rKLhTo6d0VYwaSOuR6OJWEecIr7quyQBgCPOvun2fVGrx6/7U
        D9HiXBdBDVc4vcEUviZu5V+E9xLmP9GteD1OR7TfR1AqFMPzHVvDE9UxrzEacFY4
        KPs7KP6x+8so5KvZSJKisczc+JBt+PlZisDwX9BCHJNmAYYFRm2umY7sCmLNmeoc
        Y95E6Tmpze4J1559mLM7nuzOpnnFEii4pA5H7unMUCa9AwkLLYLOV7N8iRETgG0R
        snvH5uiVRqEB84ypItCZF+Nk5Y0/WPSWPDq/bhwyQeodEPjlIfiHKzDf9GuuT9El
        Q4dGxA0mLOKMqPDJGGc7mwTTN5iczj94gsLTfI1me1qzTzxdko/BMqsmPSUbkNXS
        wgkofT+48L00HL9zq0quHkgjoTe1Wud8tI4mG0Tl9BTFE9PUtlfdJNoEQ1dk9RcR
        UkhjMbuN3h8r9w9EVugAvbp/c7SQILXEJ6QZK2NMzO01SA5Tv7hmDh1J0lcIF1zb
        VI+rlxly/riDN6U9w35vOZEzKl3qYbAXrnRteo7MEYvc/BahvxBP0ZEGRXeoNfAj
        JLvBrkhBUVy1cH5fGs2SYIwUEKBx5nLL5NeNI1ymRKbsyJ3oTKZU+PQhfarEJD2r
        u/dZoDb/AEjxCkaM1EaDG590Bjc6ZxC1ZkF6gSK27iJRP5CCj5XoD7kIpmZFE+gc
        KpVNHHe6ef2ptOngkEDUyTmZ7z18lVCeC4sBPzrLPDnWB+cie+19/cJDJpRz0n0j
        qMkh7MY+FQ8t0AopFAy7r50nV5FlGt9rG7YaWO8j5Lv3TsPPDOxFk5IoB6AtRpr8
        tSQCCyCcdHkD3M1wI/PD9bEjuELaDG8PaVzOuj5rVyh+saZQeD9GmegsuBkDGb4g
        COtzWOQ1H0ii478rbQAxwsOEMdR5lxEFOo8mC0p4mnWJti2DzJQorQC/fjbRRv7z
        vfJamXvfEuHj3NPP9cumrskBtD+kRz/c2zgVJ8vwRgNPazdfJqGYjmFB0loVVyuu
        x+hBHOD5zyMPFrJW9MNDTiTEaQREaje5tUOfNoA1Wa4s2bVLnhHCXdMSWmiDmJQp
        HEYAIZI2OJhMe8V431t6dBx+nutApzParWqET5D0DWvlurDWFrHMnazh164RqsGu
        E4Dg6ZsRnI+PEJmroia6gYEscUfd5QSUebxIeLhNzo1Kf5JRBW93NNxhAzn9ZJ9O
        2bjvkHOJlADnfON5TsPgroXX95P/9V8DWUT+/ske1Fw43V1pIT+PtraYqrlyvow+
        uJMA2q9sRLzXnFb2vg7JdD1XA4f2eUBwzbtq8wSuQexSErWaTx5uAERDnGAWyaN2
        3xCYl8CTfF70xN7j39hG/pI0ghRLGVBmCJ5NRzNZ80SPBE/nzYy/X6pGV+vsjPoZ
        S3dBmvlBV/HzB4ljsO2pI/VjCJVNZdOWDzy18GQ/jt8/xH8R9Ld6/6tuS0HbiefS
        ZefHS5wV1KNZBK+vh08HvX/AY9WBHPH+DEbrpymn/9oAKVmhH+f73ADqVOanMPk0
        -----END RSA PRIVATE KEY-----
    ssh_keypass: testtest

    sources:
        - service: load
          use_ssh: True
          ssh_host: myremotebox.acme.net
          source: tensor.sources.linux.basic.LoadAverage
          interval: 2.0

Note: Currently Tensor will _not_ perform any host key checking.

Starting Tensor
===============

To start Tensor, simply use twistd to run the service and pass a config file::

    twistd -n tensor -c tensor.yml

If you're using the Debian package then an init script is included.
