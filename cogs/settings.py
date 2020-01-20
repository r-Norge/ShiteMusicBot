import discord

from discord.ext import commands
from cogs.utils import checks


class Settings(commands.Cog):
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

    @commands.group(name='settings', hidden=True)
    async def _set(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.current_settings.invoke(ctx)

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='serverlocale')
    async def _set_guild_locale(self, ctx, locale):
        self.bot.localizer.index_localizations()
        self.bot.aliaser.index_localizations()
        self.bot.localizer.load_localizations()
        self.bot.aliaser.load_localizations()

        if locale in self.bot.aliaser.localization_table.keys():

            self.settings.set(ctx.guild, 'locale', locale)
            locale = self.settings.get(ctx.guild, 'locale', 'default_lang')
            await ctx.send(f'Locale set to `{locale}`')
        else:
            await ctx.send(f'`{locale}` is not a valid locale.')

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='serverprefix')
    async def _set_guild_prefix(self, ctx, *prefixes):
        prefixes = list(prefixes)
        if prefixes:
            self.settings.set(ctx.guild, 'prefixes', prefixes)
        prefixes = self.settings.get(ctx.guild, 'prefixes')
        await ctx.send(f'Server prefixes: {self.format_prefixes(prefixes)}')

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='resetprefix')
    async def _reset_prefix(self, ctx):
        self.settings.set(ctx.guild, 'prefixes', None)
        prefixes = self.settings.get(ctx.guild, 'prefixes', 'default_prefix')
        await ctx.send(self.format_prefixes(prefixes))

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='modrole')
    async def set_mod_role(self, ctx, modrole: discord.Role):
        await ctx.send(f'{modrole.name} {modrole.id}')

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='threshold')
    async def set_vote_threshold(self, ctx, threshold: int = 50):
        if not 0 <= threshold <= 100:
            return await ctx.send('Must be between 0 and 100')

        self.bot.settings.set(ctx.guild, 'vote_threshold', threshold)
        threshold = self.bot.settings.get(ctx.guild, 'vote_threshold', 50)
        await ctx.send(f'Vote threshold set to {threshold}%')

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='textchannels')
    async def set_music_text(self, ctx, *channels: discord.TextChannel):
        if channels:
            channel_ids = [channel.id for channel in channels]
            self.bot.settings.set(ctx.guild, 'channels.text', channel_ids)
        else:
            self.bot.settings.set(ctx.guild, 'channels.text', None)

        textchannels = self.bot.settings.get(ctx.guild, 'channels.text')

        if textchannels:
            embed = discord.Embed(title='Music command channels set', color=ctx.me.color)
            channels = [ctx.guild.get_channel(channel) for channel in textchannels]
            mentioned = [channel.mention for channel in channels if channel is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Music command channels cleared')
            await ctx.send(embed=embed)

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='musicchannels')
    async def set_music_voice(self, ctx, *channels: discord.VoiceChannel):
        if channels:
            channel_ids = [channel.id for channel in channels]
            self.bot.settings.set(ctx.guild, 'channels.music', channel_ids)
        else:
            self.bot.settings.set(ctx.guild, 'channels.music', None)

        musicchannels = self.bot.settings.get(ctx.guild, 'channels.music')

        if musicchannels:
            embed = discord.Embed(title='Music channels set', color=ctx.me.color)
            channels = [ctx.guild.get_channel(channel) for channel in musicchannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Music channels cleared')
            await ctx.send(embed=embed)

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='listenchannels', hidden=True)
    async def set_listen_voice(self, ctx, *channels: discord.VoiceChannel):
        if channels:
            channel_ids = [channel.id for channel in channels]
            self.bot.settings.set(ctx.guild, 'channels.listen_only', channel_ids)
        else:
            self.bot.settings.set(ctx.guild, 'channels.listen_only', None)

        listenchannels = self.bot.settings.get(ctx.guild, 'channels.listen_only')

        if listenchannels:
            embed = discord.Embed(title='Listen only channels set', color=ctx.me.color)
            channels = [ctx.guild.get_channel(channel) for channel in listenchannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Listen only channels cleared')
            await ctx.send(embed=embed)

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='djroles')
    async def set_dj_roles(self, ctx, *roles: discord.Role):
        role_ids = [role.id for role in roles]
        if roles:
            self.bot.settings.set(ctx.guild, 'roles.dj', role_ids)
        else:
            self.bot.settings.set(ctx.guild, 'roles.dj', None)

        djroles = self.bot.settings.get(ctx.guild, 'roles.dj')

        if djroles:
            embed = discord.Embed(title='DJ roles set to', color=ctx.me.color)
            roles = [ctx.guild.get_role(role) for role in djroles]
            mentioned = [role.name for role in roles if role is not None]
            embed.description = ', '.join(mentioned)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='DJ roles cleared')
            await ctx.send(embed=embed)

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='maxduration')
    async def set_max_track_duration(self, ctx, duration: int = None):
        self.bot.settings.set(ctx.guild, 'duration.max', duration)

        duration = self.bot.settings.get(ctx.guild, 'duration.max')

        if duration:
            embed = discord.Embed(title='Max track duration set to', color=ctx.me.color)
            embed.description = f'{duration} minutes'
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=ctx.me.color, description='Max track length removed')
            await ctx.send(embed=embed)

    @checks.is_admin()
    @commands.guild_only()
    @_set.command(name='dynamicmax')
    async def set_track_duration_type(self, ctx, dynamic: bool = False):
        self.bot.settings.set(ctx.guild, 'duration.is_dynamic', dynamic)

        is_dynamic = self.bot.settings.get(ctx.guild, 'duration.is_dynamic')

        embed = discord.Embed(title='Max duration type set to', color=ctx.me.color)
        if is_dynamic:
            embed.description = f'Dynamic'
        else:
            embed.description = f'Static'
        await ctx.send(embed=embed)

    @commands.guild_only()
    @_set.command(name='current')
    async def current_settings(self, ctx):
        embed = discord.Embed(title='{current.title}', color=ctx.me.color)
        embed.description = '{current.description}'
        embed.set_thumbnail(url=ctx.guild.icon_url)

        prefixes = self.bot.settings.get(ctx.guild, 'prefixes', 'default_prefix')
        embed.add_field(name='{current.prefix}', value=self.format_prefixes(prefixes))

        locale = f"{self.bot.settings.get(ctx.guild, 'locale', 'default_locale')}"
        embed.add_field(name='{current.locale}', value=locale)

        threshold = self.bot.settings.get(ctx.guild, 'vote_threshold', 50)
        embed.add_field(name='{current.threshold}', value=f'{threshold}%')

        is_dynamic = self.bot.settings.get(ctx.guild, 'duration.is_dynamic', 'default_is_dynamic')
        embed.add_field(name='{current.dynamicmax}', value=is_dynamic)

        duration = self.bot.settings.get(ctx.guild, 'maxduration')
        if duration:
            embed.add_field(name='{current.maxduration}', value=f'{duration} minutes')

        textchannels = self.bot.settings.get(ctx.guild, 'channels.text')
        if textchannels:
            channels = [ctx.guild.get_channel(channel) for channel in textchannels]
            mentioned = [channel.mention for channel in channels if channel is not None]
            embed.add_field(name='{current.textchannels}', value='\n'.join(mentioned))

        voicechannels = self.bot.settings.get(ctx.guild, 'channels.music')
        if voicechannels:
            channels = [ctx.guild.get_channel(channel) for channel in voicechannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.add_field(name='{current.musicchannels}', value='\n'.join(mentioned))

        listenchannels = self.bot.settings.get(ctx.guild, 'channels.listen_only')
        if listenchannels:
            channels = [ctx.guild.get_channel(channel) for channel in listenchannels]
            mentioned = [channel.name for channel in channels if channel is not None]
            embed.add_field(name='{current.listenchannels}', value='\n'.join(mentioned))

        djroles = self.bot.settings.get(ctx.guild, 'roles.dj')
        if djroles:
            roles = [ctx.guild.get_role(role) for role in djroles]
            mentioned = [role.name for role in roles if role is not None]
            embed.add_field(name='{current.djroles}', value=', '.join(mentioned))

        embed = ctx.localizer.format_embed(embed, _guild=ctx.guild.name)
        msg = await ctx.send(embed=embed)
        return msg


def setup(bot):
    bot.add_cog(Settings(bot))
