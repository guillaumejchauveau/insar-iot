FROM gitlab.insa-rennes.fr:5050/guillaumejchauveau/iot/base

WORKDIR /usr/src/app

COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir /etc/elessar
VOLUME /etc/elessar

COPY src .

CMD [ "python", "-u", "./prod.py", "/etc/elessar/config.json" ]
