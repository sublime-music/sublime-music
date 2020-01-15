#! /bin/sh
# Technique from https://georgik.rocks/how-to-start-d-bus-in-docker-container/

dbus-uuidgen > /var/lib/dbus/machine-id
mkdir -p /var/run/dbus
dbus-daemon --config-file=/usr/share/dbus-1/system.conf --print-address
