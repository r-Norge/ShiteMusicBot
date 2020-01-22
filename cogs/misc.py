import discord
import time
import platform

from discord.ext import commands
from cogs.utils import bot_version
from lavalink import __version__ as LavalinkVersion


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_uptime(self):
        now = time.time()
        diff = int(now - self.bot.uptime)
        days, remainder = divmod(diff, 24 * 60 * 60)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, seconds = divmod(remainder, 60)
        return days, hours, minutes, seconds

    @commands.command(name='ping', hidden=True)
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
        days, hours, minutes, seconds = self.get_uptime()
        await ctx.send(f'{days}d {hours}h {minutes}m {seconds}s')

    @commands.command(name='guilds')
    @commands.is_owner()
    async def _guilds(self, ctx):
        guilds = f"{self.bot.user.name} is in:\n"
        for guild in self.bot.guilds:
            guilds += f"{guild.name}\n"
        await ctx.send(guilds)

    @commands.command()
    async def musicinfo(self, ctx):
        """
        Info about the music player
        """
        embed = discord.Embed(title='{music.title}', color=ctx.me.color)
        lavalink = self.bot.lavalink

        listeners = 0
        for guild, player in lavalink.player_manager.players:
            listeners += len(player.listeners)

        embed.add_field(name='{music.players}', value=f'{len(lavalink.player_manager.players)}')
        embed.add_field(name='{music.listeners}', value=f'{listeners}')
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name="reloadlocale")
    @commands.is_owner()
    async def reload_locale(self, ctx):
        self.bot.localizer.index_localizations()
        self.bot.localizer.load_localizations()
        await ctx.send("Localizations reloaded.")

    @commands.command(name="reloadalias")
    @commands.is_owner()
    async def reload_alias(self, ctx):
        self.bot.aliaser.index_localizations()
        self.bot.aliaser.load_localizations()
        await ctx.send("Aliases reloaded.")

    @commands.command()
    async def info(self, ctx):
        """
        Info about the bot
        """
        membercount = []
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.id in membercount:
                    pass
                else:
                    membercount.append(member.id)
        guilds = len(self.bot.guilds)
        members = len(membercount)
        days, hours, minutes, seconds = self.get_uptime()
        avatar = self.bot.user.avatar_url_as(format=None, static_format='png', size=1024)

        uptimetext = f'{days}d {hours}t {minutes}m {seconds}s'
        embed = discord.Embed(color=ctx.me.color)
        embed.set_author(name=self.bot.user.name, icon_url=avatar)
        embed.set_thumbnail(url=avatar)
        embed.set_image(url='https://cdn.discordapp.com/attachments/298524946454282250/'
                            '368118192251469835/vintage1turntable.png')
        embed.add_field(name="{bot.what}",
                        value='{bot.infotext}', inline=False)
        embed.set_footer(icon_url="https://cdn.discordapp.com/icons/532176350019321917/"
                                  "92f43a1f67308a99a30c169db4b671dd.png?size=64", text="{bot.footer_text}")
        embed.add_field(name="{bot.how}",
                        value='{bot.spectext}')
        embed.add_field(name="{bot.how_many}",
                        value='{bot.stattext}')
        embed.add_field(name="{bot.how_long}",
                        value=uptimetext)

        embed = ctx.localizer.format_embed(embed, _python_v=platform.python_version(),  _discord_v=discord.__version__,
                                           _lavalink_v=LavalinkVersion,  _guilds=guilds,  _members=members,
                                           _bot_v=bot_version.bot_version)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Misc(bot))
