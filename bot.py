import discord
import codecs
import time
import sys
import traceback
import yaml
import aiohttp

from discord.ext import commands
from discord.ext.commands.view import StringView
from cogs.utils.settingsmanager import Settings
from cogs.utils.localizer import Localizer
from cogs.utils.localizer import LocalizerWrapper
from cogs.utils.alias import Aliaser
from cogs.utils.context import Context
from cogs.utils.logger import BotLogger
from cogs.helpformatter import commandhelper
from cogs.utils.paginator import Scroller


with codecs.open("data/config.yaml", 'r', encoding='utf8') as f:
    conf = yaml.load(f, Loader=yaml.SafeLoader)


initial_extensions = [
    'cogs.cogs',
    'cogs.settings',
    'cogs.misc',
    'cogs.helpformatter'
]


on_ready_extensions = [
    'cogs.music',
    'cogs.musicevents'
]


def _get_prefix(bot, message):
    if not message.guild:
        prefix = bot.settings.default_prefix
        return commands.when_mentioned_or(prefix)(bot, message)
    prefixes = bot.settings.get(message.guild, 'prefixes', 'default_prefix')
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    def __init__(self, debug: bool=False):
        super().__init__(command_prefix=_get_prefix,
                         description=conf["bot"]["description"])

        self.settings = Settings(**conf['default server settings'])
        self.APIkeys = conf.get('APIkeys', {})

        self.localizer = Localizer(conf.get('locale path', "./localization"), conf.get('locale', 'en_en'))
        self.aliaser = Aliaser(conf.get('locale path', "./localization"), conf.get('locale', 'en_en'))

        self.session = aiohttp.ClientSession(loop=self.loop)

        self.debug = debug
        self.main_logger = logger
        self.logger = self.main_logger.bot_logger.getChild("Bot")
        self.logger.debug("Debug: %s" % debug)

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception:
                self.logger.exception("Loading of extension %s failed" % extension)

    async def on_command_error(self, ctx, err):
        if not self.debug:
            if (isinstance(err, commands.MissingRequiredArgument) or
                    isinstance(err, commands.BadArgument)):
                paginator = commandhelper(ctx, ctx.command, ctx.invoker, include_subcmd=False)
                scroller = Scroller(ctx, paginator)
                await scroller.start_scrolling()

            if isinstance(err, commands.CommandInvokeError):
                self.logger.debug("Error running command: %s\n Traceback: %s"
                                 % (ctx.command, traceback.format_exception(err.__traceback__)))
                pass

            elif isinstance(err, commands.NoPrivateMessage):
                self.logger.debug("Error running command: %s\n Traceback: %s"
                                 % (ctx.command, traceback.format_exception(err.__traceback__)))
                await ctx.send('That command is not available in DMs')
            
            elif isinstance(err, commands.CommandOnCooldown):
                await ctx.send(f"{ctx.message.author.mention} Command is on cooldown. Try again in `{err.retry_after:.1f}` seconds.")

            elif isinstance(err, commands.CheckFailure):
                self.logger.debug("Error running command: %s\n Traceback: %s"
                                 % (ctx.command, traceback.format_exception(err.__traceback__)))
                pass

            elif isinstance(err, commands.CommandNotFound):
                pass
        else:
            tb = err.__traceback__
            traceback.print_tb(tb)
            print(err)

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)

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
                self.load_extension(extension)
            except Exception as e:
                self.logger.exception("Loading of extension %s failed" % extension)

        print(f'\nLogged in as: {self.user.name}' +
              f' in {len(self.guilds)} servers.')
        print(f'Version: {discord.__version__}\n')

        await self.change_presence(activity=discord.Game(type=0,
                                   name=conf["bot"]["playing status"]),
                                   status=discord.Status.online)

    def run(self):
        try:
            super().run(conf["bot"]["token"], reconnect=True)
        except Exception as e:
            tb = e.__traceback__
            traceback.print_tb(tb)
            print(e)


def run_bot(debug: bool=False):
    bot = Bot(debug=debug)
    bot.run()


if __name__ == '__main__':
    state = False
    if 'debug' in sys.argv:
        state = True
    logger = BotLogger(state, conf.get('log_path', '/data/logs'))
    run_bot(debug=state)
