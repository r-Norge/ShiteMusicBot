FROM amd64/python:3.6.8-alpine

LABEL maintainer="Roxedus"

COPY / /app

RUN \
    apk add --no-cache git && \
    python3 -m pip install -r /app/requirements.txt


WORKDIR /app

CMD ln -sf /app/data /config && python3 /app/bot.py

VOLUME /config