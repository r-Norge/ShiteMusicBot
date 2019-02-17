import discord
import codecs
import time
import sys
import traceback
import yaml

from discord.ext import commands
from cogs.utils.settings import Settings
from cogs.utils.localizer import Localizer
from cogs.utils.localizer import LocalizerWrapper
from cogs.utils.alias import Aliaser
from cogs.utils.context import Context


initial_extensions = [
    'cogs.cogs',
    'cogs.botsettings',
    'cogs.misc'
]


with codecs.open("data/config.yaml", 'r', encoding='utf8') as f:
    conf = yaml.safe_load(f)


def _get_prefix(bot, message):
    if not message.guild:
        return bot.settings.default_prefix
    prefixes = bot.settings.get(message.guild, 'prefixes', 'default_prefix')
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    def __init__(self, debug: bool=False):
        super().__init__(command_prefix=_get_prefix,
                         description=conf["bot"]["description"])

        self.settings = Settings(**conf['default server settings'])
        self.localizer = Localizer(conf.get('locale path', "./localization"), conf.get('locale', 'en_en'))
        self.aliaser = Aliaser(conf.get('locale path', "./localization"), conf.get('locale', 'en_en'))
        self.debug = debug

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception as e:
                print(e)

    async def on_command_error(self, ctx, err):
        if not self.debug:
            if (isinstance(err, commands.MissingRequiredArgument) or
                    isinstance(err, commands.BadArgument)):
                formatter = ctx.bot.formatter
                if ctx.invoked_subcommand is None:
                    _help = await formatter.format_help_for(ctx, ctx.command)
                else:
                    _help = await formatter.format_help_for(ctx,
                                                            ctx.invoked_subcommand)

                for message in _help:
                    await ctx.send(message)

            if isinstance(err, commands.CommandInvokeError):
                pass

            elif isinstance(err, commands.NoPrivateMessage):
                await ctx.send('That command is not available in DMs')

            elif isinstance(err, commands.CheckFailure):
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
        if not ctx.command:
            command = self.aliaser.get_command(ctx.locale, ctx.invoked_with)
            if command is not None:
                ctx.command = self.get_command(command)

        if ctx.command and ctx.command.cog_name:
            ctx.localizer = LocalizerWrapper(self.localizer, ctx.locale, ctx.command.cog_name.lower())
        else:
            ctx.localizer = LocalizerWrapper(self.localizer, ctx.locale, None)

        await self.invoke(ctx)

    async def on_ready(self):
        if not hasattr(self, 'uptime'):
            self.uptime = time.time()
            if self.debug:
                print('\n\nDebug mode')

        print(f'\nLogged in as: {self.user.name}' +
              f' in {len(self.guilds)} servers.')
        print(f'Version: {discord.__version__}\n')

        self.load_extension('cogs.music')
        self.load_extension('cogs.musicevents')

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
    if 'debug' in sys.argv:
        run_bot(debug=True)
    else:
        run_bot(debug=False)
