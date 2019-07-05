FROM amd64/python:3.7.3-alpine

LABEL maintainer="Roxedus"

COPY / /app

RUN \
    apk add --no-cache git && \
    python3 -m pip install -r /app/requirements.txt


WORKDIR /app

CMD cp -u /app/data/config.yaml.example /config/config.yaml.example && python3 /app/bot.py --data-directory /config

VOLUME /config
