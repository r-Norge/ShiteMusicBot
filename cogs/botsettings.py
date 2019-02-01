import discord
import os
import json
import codecs
from discord.ext import commands
from cogs.utils import checks

class BotSettings:
    def __init__(self, bot):
        self.bot = bot
        self.settings = self.bot.settings

    @checks.is_admin()
    @commands.group(name='set', hidden=True)
    async def _set(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'),
                             ctx.command.qualified_name)

    @commands.guild_only()
    @_set.command(name='serverlocale')
    async def _set_guild_locale(self, ctx, locale):
        self.settings.set_locale(ctx.guild.id, locale)
        locale = self.settings.get_locale(ctx.guild.id)
        await ctx.send(f'Locale set to {locale}')

    @commands.guild_only()
    @_set.command(name='serverprefix')
    async def _set_guild_prefix(self, ctx, *prefixes):
        prefixes = list(prefixes)
        if prefixes != []:
            self.settings.set_prefix(ctx.guild.id, prefixes)
        prefixes = self.settings.get_prefix(ctx.guild.id)
        await ctx.send(self.format_prefixes(prefixes))

    @commands.guild_only()
    @_set.command(name='resetprefix')
    async def _reset_prefix(self, ctx):
        self.settings.set_prefix(ctx.guild.id, None)
        prefixes = self.settings.get_prefix(ctx.guild.id)
        await ctx.send(self.format_prefixes(prefixes))

    def format_prefixes(self, prefixes):
        if prefixes is None:
            prefixes = [self.bot.settings.default_prefix]
        formatted = 'Server prefixes: '
        for prefix in prefixes:
            formatted += f'`{prefix}`, '
        return formatted[:-2]

    @commands.guild_only()
    @_set.command(name='setmodrole')    
    async def set_mod_role(self, ctx, modrole: discord.Role):
        await ctx.send(f'{modrole.name} {modrole.id}')

    @commands.guild_only()
    @_set.command(name='current')
    async def current_settings(self, ctx):
        embed = discord.Embed(title='Settings', color=ctx.me.color)
        embed.description = f'Current settings for {ctx.guild.name}'
        embed.set_thumbnail(url=ctx.guild.icon_url)

        prefixes = self.bot.settings.get_prefix(ctx.guild.id)
        locale = f'`{self.bot.settings.get_locale(ctx.guild.id)}`'
        embed.add_field(name='Locale', value=locale)
        embed.add_field(name='Prefix', value=self.format_prefixes(prefixes))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(BotSettings(bot))
