FROM amd64/python:3.8.3-alpine

LABEL maintainer="Roxedus"

COPY / /app

RUN \
    apk add --no-cache --update gcc musl-dev python3-dev git && \
    python3 -m pip install -r /app/requirements.txt


WORKDIR /app

CMD cp -u /app/data/config.yaml.example /config/config.yaml.example && python3 /app/bot.py --data-directory /config

VOLUME /config
