import traceback

from discord.ext import commands

from bot import MusicBot
from musicbot.utils.userinteraction import ClearMode, Scroller

from .helpformatter import commandhelper


class CogManager(commands.Cog):
    def __init__(self, bot: MusicBot):
        self.bot: MusicBot = bot
        self.settings = self.bot.settings

    @commands.group(name='cogmanager', hidden=True)
    @commands.is_owner()
    async def _cogmanager(self, ctx):
        if ctx.invoked_subcommand is None:
            ctx.localizer.prefix = 'help'  # Ensure the bot looks for locales in the context of help, not cogmanager.
            paginator = commandhelper(ctx, ctx.command, ctx.invoker, include_subcmd=True)
            scroller = Scroller(ctx, paginator)
            await scroller.start_scrolling(ClearMode.AnyExit)

    @_cogmanager.command()
    @commands.is_owner()
    async def load(self, ctx, *, module):
        """Loads a module."""
        try:
            await self.bot.load_extension(f'musicbot.cogs.{module}')
            await ctx.send(f'{module} loaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogmanager.command()
    @commands.is_owner()
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        if module == "cogmanager":
            return await ctx.send('Unloading this cog is not allowed')
        try:
            await self.bot.unload_extension(f'musicbot.cogs.{module}')
            await ctx.send(f'{module} unloaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogmanager.command(name='reload')
    @commands.is_owner()
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        try:
            await self.bot.unload_extension(f'musicbot.cogs.{module}')
            await self.bot.load_extension(f'musicbot.cogs.{module}')
            await ctx.send(f'{module} reloaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogmanager.command(name='reloadall')
    @commands.is_owner()
    async def _relaod_all(self, ctx):
        """Reloads all extensions."""
        try:
            for extension in self.bot.extensions:
                if extension == 'musicbot.cogs.cogmanager':
                    continue
                await self.bot.unload_extension(f'{extension}')
                await self.bot.load_extension(f'{extension}')
            await ctx.send('Extensions reloaded')
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')

    @_cogmanager.command(name='shutdown')
    @commands.is_owner()
    async def _shutdown(self, ctx):
        """Logs out and stops."""
        if lavalink := self.bot.lavalink:
            lavalink.player_manager.players.clear()
        await self.bot.close()


async def setup(bot):
    await bot.add_cog(CogManager(bot))
