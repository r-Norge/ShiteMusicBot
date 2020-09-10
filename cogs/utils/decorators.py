# Discord Packages
import discord
from discord.ext import commands

import functools
import inspect

# Bot Utilities
from cogs.utils.music_errors import WrongVoiceChannelError


def require_voice_connection(should_connect=False):
    """
    Checks if the bot is in a valid voice channel for the command
    should_connect indicates whether the bot should try to join a channel
    """
    def ensure_voice_proper(func):
        @functools.wraps(func)
        async def ensure_voice_inner(self, ctx, *command_args, **kwargs):
            """ This check ensures that the bot and command author are in the same voicechannel. """

            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if not ctx.author.voice or not ctx.author.voice.channel:
                raise commands.CommandInvokeError('Join a voicechannel first.')

            if not player.is_connected:
                if not should_connect:
                    raise commands.CommandInvokeError('Not connected.')

                user_voice_channel = ctx.author.voice.channel
                permissions = user_voice_channel.permissions_for(ctx.me)

                if not permissions.connect or not permissions.speak:  # Check user limit too?
                    raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

                # Check against music channel restrictions in bot settings
                if voice_channels := self.bot.settings.get(ctx.guild, 'channels.music', []):
                    if user_voice_channel.id not in voice_channels:
                        raise WrongVoiceChannelError(
                            'You need to be in the right voice channel', channels=voice_channels)

                player.store('channel', ctx.channel.id)
                await self.connect_to(ctx.guild.id, str(ctx.author.voice.channel.id))

            elif int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You need to be in my voicechannel.')

            await func(self, ctx, *command_args, **kwargs)

        return ensure_voice_inner
    return ensure_voice_proper


def require_playing(require_user_listening=False):
    """
    Checks if the bot is currently playing a track
    ensure_user_listening: also checks if the user is listening to the bot
    """
    def ensure_play(func):
        @functools.wraps(func)
        async def ensure_play_inner(self, ctx, *command_args, **kwargs):

            if player := self.bot.lavalink.player_manager.get(ctx.guild.id):

                if not player.is_playing:
                    raise commands.CommandInvokeError('Not playing')

                if require_user_listening and (ctx.author not in player.listeners):
                    raise commands.CommandInvokeError('Not listening')

            else:
                raise Exception('Player object does not yet exist')

            await func(self, ctx, *command_args, **kwargs)

        return ensure_play_inner
    return ensure_play


def require_queue(require_member_queue=False, require_author_queue=False):
    """
    Checks if there is something queued
    require_member_queue also checks if the queue of a member is empty, only works when member is an argument
    """
    def ensure_queue(func):
        if require_member_queue:
            inspection = inspect.getfullargspec(func)
            assert 'member' in inspection.kwonlyargs, """require_member_error can only be used
             on commands with a member keyword argument"""
            # assert str(inspection.annotations['member']) == "<class 'discord.member.Member'>", """
            # Member must be a discord member type"""

        @functools.wraps(func)
        async def ensure_queue_inner(self, ctx, *command_args, **kwargs):
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)

            if require_member_queue:
                try:
                    if member := kwargs['member']:  # Ignore if member is None
                        user_queue = player.user_queue(member.id)
                        if not user_queue:
                            embed = discord.Embed(description='{queue.user_empty}', color=ctx.me.color)
                            embed = ctx.localizer.format_embed(embed, _user=member.display_name)
                            return await ctx.send(embed=embed)
                except KeyError:
                    raise Exception("require_member_error can only be used on commands with a member keyword argument")

            if require_author_queue:
                user_queue = player.user_queue(ctx.author.id)
                if not user_queue:
                    embed = discord.Embed(description='{my_queue}', color=ctx.me.color)
                    embed = ctx.localizer.format_embed(embed)
                    return await ctx.send(embed=embed)

            if player.queue.empty:
                embed = discord.Embed(description='{queue.empty}', color=ctx.me.color)
                embed = ctx.localizer.format_embed(embed)
                return await ctx.send(embed=embed)

            await func(self, ctx, *command_args, **kwargs)
        return ensure_queue_inner
    return ensure_queue
