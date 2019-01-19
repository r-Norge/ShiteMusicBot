FROM amd64/python:3.7.2-alpine

LABEL maintainer="Roxedus"

COPY / /app

RUN python3 -m pip install -r /app/requirements.txt

WORKDIR /app

CMD python3 /app/bot.py

VOLUME /config