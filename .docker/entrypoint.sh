#!/bin/sh

# start services
mkdir -p /var/run/dbus
dbus-daemon --system
bluetoothd &

# reset bluetooth adapter by restarting it
hciconfig hci0 down
hciconfig hci0 up

exec "$@"
