FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y bluez \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

ENV DBUS_SYSTEM_BUS_ADDRESS unix:path=/host/run/dbus/system_bus_socket
