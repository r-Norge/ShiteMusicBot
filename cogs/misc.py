import discord
import os
import asyncio
import time
import random

from discord.ext import commands
from cogs.utils import checks

class Misc:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping', hidden=True)
    @checks.is_mod()
    async def _ping(self, ctx):
            start = time.perf_counter()
            message = await ctx.send('Ping...')
            end = time.perf_counter()
            duration = int((end - start) * 1000)
            edit = f'Pong!\nPing: {duration}ms' \
                + f' | websocket: {int(self.bot.latency * 1000)}ms'
            await message.edit(content=edit)

    @commands.command(name='uptime', hidden=True)
    async def _uptime(self, ctx):
        now = time.time()
        diff = int(now - self.bot.uptime)
        days, remainder = divmod(diff, 24 * 60 * 60)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(f'{days}d {hours}h {minutes}m {seconds}s')

    @commands.command(name='guilds')
    @checks.is_owner()
    async def _guilds(self, ctx):
        guilds = f"{self.bot.user.name} is in:\n"
        for guild in self.bot.guilds:
            guilds += f"{guild.name}\n"
        await ctx.send(guilds)

    @commands.command()
    async def info(self, ctx, *, channel: str=None):
        """
        Info om LovherkBot
        """
        avatar = self.bot.user.avatar_url_as(format=None,
                                             static_format='png',
                                             size=1024)
        infotext = f'Shite Music Bot'
        embed = discord.Embed(color=0xD9C04D)
        embed.set_author(name=self.bot.user.name, icon_url=avatar)
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="Hva?",
                        value=infotext, inline=False)
        embed.set_footer(icon_url="https://i.imgur.com/dE6JaeT.gif",
                         text="Laget av /r/Norge")
        await ctx.send(embed=embed)

    @commands.command()
    @checks.is_even()
    async def only_me(self, ctx):
        await ctx.send('Only you!')


def setup(bot):
    bot.add_cog(Misc(bot))
