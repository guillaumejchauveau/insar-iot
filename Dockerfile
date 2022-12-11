FROM python:3.10-slim

WORKDIR /usr/src/app

RUN apt-get update
RUN apt-get install -y bluez

ENV DBUS_SYSTEM_BUS_ADDRESS unix:path=/host/run/dbus/system_bus_socket

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir /etc/elessar
VOLUME /etc/elessar

COPY src .

CMD [ "python", "-u", "./prod.py", "/etc/elessar/config.json" ]
