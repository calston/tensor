#!/bin/bash

if [ ! -d /etc/tensor ]; 
then
    mkdir -p /etc/tensor
    cat >/etc/tensor/tensor.yml <<EOL
# Default event TTL
ttl: 60.0
# De-queue interval
interval: 1.0

# TCP Output
outputs:
    - output: tensor.outputs.riemann.RiemannTCP
      server: 127.0.0.1
      port: 5555

# Sources
sources:
    - service: load
      source: tensor.sources.linux.basic.LoadAverage
      interval: 2.0

    - service: cpu
      source: tensor.sources.linux.basic.CPU
      interval: 2.0
      critical: {
        cpu: "> 0.8"
      }

    - service: memory
      source: tensor.sources.linux.basic.Memory
      interval: 2.0
EOL
fi

if [ ! -d /var/lib/tensor ];
then
    mkdir -p /var/lib/tensor
    cp /tmp/*.lf /var/lib/tensor/
fi

update-rc.d tensor defaults
service tensor status >/dev/null 2>&1

if [ "$?" -gt "0" ];
then
    service tensor start 2>&1
else
    service tensor restart 2>&1
fi 

exit 0
