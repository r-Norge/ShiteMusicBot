# Discord Packages
from discord.ext import commands

import traceback


class Cogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = self.bot.settings

    @commands.group(name='cogs', hidden=True)
    @commands.is_owner()
    async def _cogs(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'),
                             ctx.command.qualified_name)

    @_cogs.command()
    @commands.is_owner()
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            self.bot.load_extension(f'cogs.{module}')
            await ctx.send(f'{module} loaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command()
    @commands.is_owner()
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        if module == "cogs":
            return await ctx.send('Unloading this cog is not allowed')
        try:
            self.bot.unload_extension(f'cogs.{module}')
            await ctx.send(f'{module} unloaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command(name='reload')
    @commands.is_owner()
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            self.bot.unload_extension(f'cogs.{module}')
            self.bot.load_extension(f'cogs.{module}')
            await ctx.send(f'{module} reloaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command(name='reloadall')
    @commands.is_owner()
    async def _relaod_all(self, ctx):
        """Reloads all extensions"""
        try:
            for extension in self.bot.extensions:
                if extension == 'cogs.cogs':
                    continue
                self.bot.unload_extension(f'{extension}')
                self.bot.load_extension(f'{extension}')
            await ctx.send('Extensions reloaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogs.command(name='shutdown')
    @commands.is_owner()
    async def _shutdown(self, ctx):
        """Logs out and stops."""
        self.bot.lavalink.player_manager.players.clear()
        await self.bot.logout()


def setup(bot):
    bot.add_cog(Cogs(bot))
