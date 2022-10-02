# Shite Music Bot
A discord music bot you can self host


## Features

- Translations, get the bot in your preferred langauge! Works for both commands and replies.
- Round Robin style queue, you won't have to wait forever for your songs to play.
- Nice interactive menus
- Noice per server customization options, including per server localization.
- Toit embeds.
- DJ roles
- Lyrics command that sometimes gives the correct lyrics

### Requirements
- Python 3.10 or greater

### Setup

1. Change or copy data/config.yaml.example to config.yaml
2. Create or find a [lavalink](https://github.com/Freyacodes/Lavalink) server you can use.
3. Add your bot token and lavalink server to the bot settings in your config.yaml.
4. Edit any other settings you want.
5. (Optional but recommended) Create a virtual environment and activate it.
6. install requirements `python -m pip install -r requirements.txt`
7. run the bot `python bot.py` :)

### Docker

#### Compose Example

````yaml
version: '3'
networks:
  internal:
    driver: bridge

services:
    backbone:
        hostname: lavalink
        image: fredboat/lavalink:dev
        ports:
        - 2333:2333
        networks:
            internal:
                aliases:
                  - lavalink
        volumes:
          - /compose/BottStack/lavalink/application.yml:/opt/Lavalink/application.yml
    bot:
        container_name: ProdMaster
        image: rnorge/music
        networks:
          - internal
        command: python3 bot.py
        volumes:
          - /compose/BottStack/ProdBetaMaster/script:/diks
          - /compose/BottStack/ProdBetaMaster/data:/app/data
````
