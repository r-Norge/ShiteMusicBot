# Discord Packages
import discord
import lavalink
from discord.ext import commands
from discord.flags import MemberCacheFlags

import codecs
import os
import time
import traceback
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Optional

import aiohttp
import yaml

# Bot Utilities
from musicbot.utils.localisation import Aliaser, LocalizedContext, Localizer, LocalizerWrapper
from musicbot.utils.logger import BotLogger
from musicbot.utils.settingsmanager import Settings

on_ready_extensions = [
    'musicbot.cogs.nodemanager',
    'musicbot.cogs.errors',
    'musicbot.cogs.cogmanager',
    'musicbot.cogs.settings',
    'musicbot.cogs.misc',
    'musicbot.cogs.helpformatter'
]


def _get_prefix(bot, message):
    if not message.guild:
        prefix = bot.settings.default_prefix
        return commands.when_mentioned_or(prefix)(bot, message)
    prefixes = bot.settings.get(message.guild, 'prefixes', 'default_prefix')
    return commands.when_mentioned_or(*prefixes)(bot, message)


class MusicBot(commands.Bot):
    def __init__(self, datadir, debug: bool = False):
        intents = discord.Intents.all()
        super().__init__(command_prefix=_get_prefix,
                         description=conf["bot"]["description"],
                         intents=intents,
                         member_cache_flags=MemberCacheFlags.from_intents(intents)
                         )

        self.settings = Settings(datadir, **conf['default server settings'])
        self.APIkeys = conf.get('APIkeys', {})

        self.localizer = Localizer(conf.get('locale path', "./localization"), conf.get('locale', 'en_en'))
        self.aliaser = Aliaser(conf.get('locale path', "./localization"), conf.get('locale', 'en_en'))

        self.datadir = datadir
        self.debug = debug
        self.main_logger = logger
        self.logger = self.main_logger.bot_logger.getChild("Bot")
        self.logger.debug("Debug: %s" % debug)
        self.lavalink: Optional[lavalink.Client] = None

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=LocalizedContext)

        # Replace aliases with commands
        ctx = self.aliaser.get_command(ctx)

        # Add the localizer
        if ctx.command and ctx.command.cog_name:
            ctx.localizer = LocalizerWrapper(self.localizer, ctx.locale, ctx.command.cog_name.lower())
        else:
            ctx.localizer = LocalizerWrapper(self.localizer, ctx.locale, None)

        await self.invoke(ctx)

    async def on_ready(self):
        if not hasattr(self, 'uptime'):
            self.uptime = time.time()

        for extension in on_ready_extensions:
            try:
                self.logger.debug("Loading extension %s" % extension)
                await self.load_extension(extension)
            except Exception:
                self.logger.exception("Loading of extension %s failed" % extension)

        if self.user:
            info = f'Logged in as: {self.user.name} in {len(self.guilds)} servers.'
            border = "="*len(info)
            self.logger.info(border)
            self.logger.info(info)
            self.logger.info(f'Version: {discord.__version__}')
            self.logger.info(border)
        self.logger.debug("Bot Ready")

        self.session = aiohttp.ClientSession(loop=self.loop)
        await self.change_presence(activity=discord.Game(type=0,
                                                         name=conf["bot"]["playing status"]),
                                   status=discord.Status.online)

    def run(self):
        try:
            super().run(conf["bot"]["token"], reconnect=True)
        except Exception as e:
            tb = e.__traceback__
            traceback.print_tb(tb)
            self.logger.exception(e)


def run_bot(datadir, debug: bool = False):
    bot = MusicBot(datadir, debug=debug)
    bot.run()


if __name__ == '__main__':
    parser = ArgumentParser(prog='Shite Music Bot',
                            description='Discord music bot utilizing discord.py, lavalink and lavalink.py',
                            formatter_class=RawTextHelpFormatter)

    parser.add_argument("-D", "--debug", action='store_true', help='Sets debug to true')
    parser.add_argument("-d", "--data-directory", help='Define an alternate data directory location')

    args = parser.parse_args()
    if args.debug or os.environ.get('debug'):
        is_debug = True
    else:
        is_debug = False

    if args.data_directory:
        datadir = str(args.data_directory)
    else:
        datadir = "data"

    print(f"Data folder: {datadir}")

    with codecs.open(f"{datadir}/config.yaml", 'r', encoding='utf8') as f:
        conf = yaml.load(f, Loader=yaml.SafeLoader)

    logger = BotLogger(is_debug, conf.get('log_path', f'{datadir}/logs'))
    run_bot(debug=is_debug, datadir=datadir)
