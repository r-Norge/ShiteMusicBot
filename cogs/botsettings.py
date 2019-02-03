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

    def format_prefixes(self, prefixes):
        if prefixes is None:
            prefixes = [self.bot.settings.default_prefix]
        formatted = ''
        for prefix in prefixes:
            formatted += f'`{prefix}`, '
        return formatted[:-2]

    @checks.is_admin()
    @commands.group(name='set', hidden=True)
    async def _set(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.current_settings.invoke(ctx)

    @commands.guild_only()
    @_set.command(name='serverlocale')
    async def _set_guild_locale(self, ctx, locale):
        self.settings.set(ctx.guild.id, 'locale', locale)
        locale = self.settings.get(ctx.guild.id, 'locale', 'default_lang')
        await ctx.send(f'Locale set to {locale}')

    @commands.guild_only()
    @_set.command(name='serverprefix')
    async def _set_guild_prefix(self, ctx, *prefixes):
        prefixes = list(prefixes)
        if prefixes != []:
            self.settings.set(ctx.guild.id, 'prefixes', prefixes)
        prefixes = self.settings.get(ctx.guild.id, 'prefixes')
        await ctx.send(f'Server prefixes: {self.format_prefixes(prefixes)}')

    @commands.guild_only()
    @_set.command(name='resetprefix')
    async def _reset_prefix(self, ctx):
        self.settings.set(ctx.guild.id, 'prefixes', None)
        prefixes = self.settings.get(ctx.guild.id, 'prefixes', 'default_prefix')
        await ctx.send(self.format_prefixes(prefixes))

    @commands.guild_only()
    @_set.command(name='modrole')
    async def set_mod_role(self, ctx, modrole: discord.Role):
        await ctx.send(f'{modrole.name} {modrole.id}')

    @commands.guild_only()
    @_set.command(name='threshold')
    async def set_vote_threshold(self, ctx, threshold: int=50):
        if not 0 <= threshold <= 100:
            return await ctx.send('Must be between 0 and 100')

        self.bot.settings.set(ctx.guild.id, 'vote_threshold', threshold)
        threshold = self.bot.settings.get(ctx.guild.id, 'vote_threshold', 50)
        await ctx.send(f'Vote threshold set to {threshold}%')

    @commands.guild_only()
    @_set.command(name='textchannels')
    async def set_music_text(self, ctx, *channels: discord.TextChannel):
        if channels:
            channel_ids = [channel.id for channel in channels]
            self.bot.settings.set(ctx.guild.id, 'channels.text', channel_ids)
        else:
            self.bot.settings.set(ctx.guild.id, 'channels.text', None)

        textchannels = self.bot.settings.get(ctx.guild.id, 'channels.text')

        if textchannels:
            embed = discord.Embed(title='Music command channels set', color=ctx.me.color)
            channels = [ctx.guild.get_channel(channel) for channel in textchannels]
            mentioned = [channel.mention for channel in channels if channel is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Music command channels cleared')
            await ctx.send(embed=embed)

    @commands.guild_only()
    @_set.command(name='voicechannels')
    async def set_music_voice(self, ctx, *channels: discord.VoiceChannel):
        if channels:
            channel_ids = [channel.id for channel in channels]
            self.bot.settings.set(ctx.guild.id, 'channels.voice', channel_ids)
        else:
            self.bot.settings.set(ctx.guild.id, 'channels.voice', None)

        voicechannels = self.bot.settings.get(ctx.guild.id, 'channels.voice')

        if voicechannels:
            embed = discord.Embed(title='Music channels set', color=ctx.me.color)
            channels = [ctx.guild.get_channel(channel) for channel in voicechannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Music channels cleared')
            await ctx.send(embed=embed)

    @commands.guild_only()
    @_set.command(name='listenchannels')
    async def set_listen_voice(self, ctx, *channels: discord.VoiceChannel):
        if channels:
            channel_ids = [channel.id for channel in channels]
            self.bot.settings.set(ctx.guild.id, 'channels.listen_only', channel_ids)
        else:
            self.bot.settings.set(ctx.guild.id, 'channels.listen_only', None)

        listenchannels = self.bot.settings.get(ctx.guild.id, 'channels.listen_only')

        if listenchannels:
            embed = discord.Embed(title='Listen only channels set', color=ctx.me.color)
            channels = [ctx.guild.get_channel(channel) for channel in listenchannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Listen only channels cleared')
            await ctx.send(embed=embed)

    @commands.guild_only()
    @_set.command(name='djroles')
    async def set_dj_roles(self, ctx, *roles: discord.Role):
        role_ids = [role.id for role in roles]
        if roles:
            self.bot.settings.set(ctx.guild.id, 'roles.dj', role_ids)
        else:
            self.bot.settings.set(ctx.guild.id, 'roles.dj', None)

        djroles = self.bot.settings.get(ctx.guild.id, 'roles.dj')

        if djroles:
            embed = discord.Embed(title='DJ roles set to', color=ctx.me.color)
            roles = [ctx.guild.get_role(role) for role in djroles]
            mentioned = [role.name for role in roles if role is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='DJ roles cleared')
            await ctx.send(embed=embed)

    @commands.guild_only()
    @_set.command(name='current')
    async def current_settings(self, ctx):
        embed = discord.Embed(title='Settings', color=ctx.me.color)
        embed.description = f'Current settings for {ctx.guild.name}'
        embed.set_thumbnail(url=ctx.guild.icon_url)

        prefixes = self.bot.settings.get(ctx.guild.id, 'prefixes', 'default_prefix')
        embed.add_field(name='Prefix', value=self.format_prefixes(prefixes))

        locale = f"{self.bot.settings.get(ctx.guild.id, 'locale', 'default_locale')}"
        embed.add_field(name='Locale', value=locale)

        threshold = self.bot.settings.get(ctx.guild.id, 'vote_threshold', 50)
        embed.add_field(name='Vote threshold', value=f'{threshold}%')

        textchannels = self.bot.settings.get(ctx.guild.id, 'channels.text')
        if textchannels:
            channels = [ctx.guild.get_channel(channel) for channel in textchannels]
            mentioned = [channel.mention for channel in channels if channel is not None]
            embed.add_field(name='Text channels', value='\n'.join(mentioned))

        voicechannels = self.bot.settings.get(ctx.guild.id, 'channels.voice')
        if voicechannels:
            channels = [ctx.guild.get_channel(channel) for channel in voicechannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.add_field(name='Voice channels', value='\n'.join(mentioned))

        listenchannels = self.bot.settings.get(ctx.guild.id, 'channels.listen_only')
        if listenchannels:
            channels = [ctx.guild.get_channel(channel) for channel in listenchannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.add_field(name='Listen only channels', value='\n'.join(mentioned))

        djroles = self.bot.settings.get(ctx.guild.id, 'roles.dj')
        if djroles:
            roles = [ctx.guild.get_role(role) for role in djroles]
            mentioned = [role.name for role in roles if role is not None]
            embed.add_field(name='Dj roles', value=', '.join(mentioned))

        msg = await ctx.send(embed=embed)
        return msg


def setup(bot):
    bot.add_cog(BotSettings(bot))
