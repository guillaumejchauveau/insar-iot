FROM gitlab.insa-rennes.fr:5050/guillaumejchauveau/base-images/python-bluez:3.10-slim

WORKDIR /usr/src/app

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir /etc/elessar
VOLUME /etc/elessar

COPY src .

CMD [ "python", "-u", "./prod.py", "/etc/elessar/config.json" ]
