FROM python:3.10-slim

WORKDIR /usr/src/app

RUN apt-get update
RUN apt-get install -y bluez

COPY .docker/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT [ "entrypoint.sh" ]

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src .

CMD [ "python", "-u", "./main.py" ]
