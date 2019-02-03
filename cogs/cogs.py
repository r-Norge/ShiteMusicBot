import discord
import os
import json
import codecs
import traceback
from discord.ext import commands
from cogs.utils import checks

class Cogs:
    def __init__(self, bot):
        self.bot = bot
        self.settings = self.bot.settings

    @commands.group(name='cogs')
    @checks.is_owner()
    async def _cogs(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'),
                             ctx.command.qualified_name)

    @_cogs.command()
    @checks.is_owner()
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            self.bot.load_extension(f'cogs.{module}')
            await ctx.send(f'{module} loaded')
        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc(e)}\n```')

    @_cogs.command()
    @checks.is_owner()
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        try:
            self.bot.unload_extension(f'cogs.{module}')
            await ctx.send(f'{module} unloaded')
        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command(name='reload')
    @checks.is_owner()
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            self.bot.unload_extension(f'cogs.{module}')
            self.bot.load_extension(f'cogs.{module}')
            await ctx.send(f'{module} reloaded')
        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command(name='reloadall')
    @checks.is_owner()
    async def _relaod_all(self, ctx):
        """Reloads all extensions"""
        try:
            for extension in self.bot.extensions:
                if extension == 'cogs.cogs':
                    continue
                self.bot.unload_extension(f'{extension}')
                self.bot.load_extension(f'{extension}')
            await ctx.send('Extensions reloaded')
        except Exception as e:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command(name='shutdown')
    @checks.is_owner()
    async def _shutdown(self, ctx):
        """Logs out and stops."""
        self.bot.lavalink.players.clear()
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Cogs(bot))
