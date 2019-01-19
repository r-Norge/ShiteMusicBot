FROM amd64/python:3.7.2-alpine

LABEL maintainer="Roxedus"

COPY / /app

RUN \
    apk add --no-cache git && \
    python3 -m pip install -r /app/requirements.txt && \
    chown -R abc:abc \
    /config \
    /app


WORKDIR /app

CMD ln -sf /app/data /config && python3 /app/bot.py

VOLUME /config