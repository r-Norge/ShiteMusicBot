import json
import os
import codecs
import discord
import time

from discord.ext import commands
from cogs.utils.settings import Settings


initial_extension = [
    'cogs.cogs',
    'cogs.botsettings',
    'cogs.misc',
    'cogs.music'
]


with codecs.open("config.json", 'r', encoding='utf8') as f:
    config = json.load(f)


def _get_prefix(bot, message):
    if not message.guild:
        return default_prefix
    prefixes = bot.settings.get_prefix(message.guild.id)
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=_get_prefix,
                         description=config["description"])

        self.settings = Settings(**config)

        for extension in initial_extension:
            try:
                self.load_extension(extension)
            except Exception as e:
                print(e)

    async def on_command_error(self, ctx, err):
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
            await ctx.send("Denne kommandoen er ikke tilgjengelig i DMs")

        elif isinstance(err, commands.CheckFailure):
            pass

        elif isinstance(err, commands.CommandNotFound):
            pass

    async def on_ready(self):
        if not hasattr(self, 'uptime'):
            self.uptime = time.time()

        print(f'\nLogged in as: {self.user.name}' +
              f' in {len(self.guilds)} servers.')
        print(f'Version: {discord.__version__}\n')

        await self.change_presence(activity=discord.Game(type=0,
                                   name=config["playing"]),
                                   status=discord.Status.online)

    def run(self):
        try:
            super().run(config["token"], reconnect=True)
        except Exception as e:
            print('ifkn', e)


def run_bot():
    bot = Bot()
    bot.run()

if __name__ == '__main__':
    run_bot()
