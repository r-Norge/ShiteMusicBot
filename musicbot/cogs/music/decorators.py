# Discord Packages
import discord

import asyncio
import functools
import inspect
import math

# Bot Utilities
from musicbot.utils.mixplayer.player import MixPlayer
from ...utils.checks import is_dj
from . import music_errors
from .voice_client import BasicVoiceClient


def require_voice_connection(should_connect=False):
    """
    Checks if the bot is in a valid voice channel for the command
    should_connect indicates whether the bot should try to join a channel
    """
    def ensure_voice(func):
        @functools.wraps(func)
        async def ensure_voice_inner(self, ctx, *command_args, **kwargs):
            """ This check ensures that the bot and command author are in the same voicechannel. """

            player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
            if not player:
                raise music_errors.MusicError("ensure voice could not get lavalink player")

            if not ctx.author.voice or not ctx.author.voice.channel:
                raise music_errors.UserNotConnectedError('Join a voicechannel first.')

            if not player.is_connected:
                if not should_connect:
                    raise music_errors.BotNotConnectedError('Not connected.')

                user_voice_channel = ctx.author.voice.channel
                permissions = user_voice_channel.permissions_for(ctx.me)

                if not permissions.connect or not permissions.speak:  # Check user limit too?
                    raise music_errors.MissingPermissionsError('I need the `CONNECT` and `SPEAK` permissions.')

                if (len(user_voice_channel.members) == user_voice_channel.user_limit) and not permissions.administrator:
                    raise music_errors.VoiceChannelFullError('The channel is currently full', user_voice_channel)

                # Check against music channel restrictions in bot settings
                if voice_channels := self.bot.settings.get(ctx.guild, 'channels.music', []):
                    if user_voice_channel.id not in voice_channels:
                        raise music_errors.WrongVoiceChannelError(
                            'You need to be in the right voice channel', channels=voice_channels)

                player.store('channel', ctx.channel.id)
                await ctx.author.voice.channel.connect(cls=BasicVoiceClient)

            elif player.channel_id and int(player.channel_id) != ctx.author.voice.channel.id:
                bot_channel = self.bot.get_channel(int(player.channel_id))
                raise music_errors.UserInDifferentVoiceChannelError('You need to be in my voice channel',
                                                                    channel=bot_channel)

            await func(self, ctx, *command_args, **kwargs)

        return ensure_voice_inner
    return ensure_voice


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
                    raise music_errors.RequirePlayingError('Not playing')

                if require_user_listening and (ctx.author not in player.listeners):
                    raise music_errors.RequireListeningError('Not listening')

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
                        user_queue = player.user_queue(member)
                        if not user_queue:
                            embed = discord.Embed(description='{queue.user_empty}', color=ctx.me.color)
                            embed = ctx.localizer.format_embed(embed, _user=member.display_name)
                            return await ctx.send(embed=embed)
                except KeyError:
                    raise Exception("require_member_error can only be used on commands with a member keyword argument")

            if require_author_queue:
                user_queue = player.user_queue(ctx.author)
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


def voteable(requester_override=False, DJ_override=False, react_to_vote=False):
    def make_voteable(func):
        @functools.wraps(func)
        async def voteable_inner(self, ctx, *command_args, **kwargs):
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            player.add_vote(func.__name__, ctx.author)

            total = len(player.listeners)
            votes = len(player.get_voters(func.__name__))
            threshold = self.bot.settings.get(ctx.guild, 'vote_threshold', 'default_threshold')

            enough_votes = votes/total >= threshold/100
            DJ = DJ_override and is_dj(ctx)
            requester = player.current is None or (player.current.requester == ctx.author.id and requester_override)

            if enough_votes or requester or DJ:
                await func(self, ctx, *command_args, **kwargs)
                player.clear_votes()

            elif react_to_vote:
                embed = discord.Embed(title="Votes",
                                      description=f"{votes} out of {math.ceil(total*threshold/100)} required votes.",
                                      color=ctx.me.color)
                embed.set_footer(text=f'{{requested_by}} {ctx.author.name}', icon_url=ctx.author.display_avatar.url)
                msg = await ctx.send(embed=ctx.localizer.format_embed(embed))
                await msg.add_reaction('👍')

                def check(reaction, user):
                    if not reaction.message.id == msg.id:
                        return False

                    if user is None or user not in player.listeners:
                        return False

                    if reaction.emoji == '👍' and user.id not in player.get_voters(func.__name__):
                        player.add_vote(func.__name__, user)
                        return True
                    return False

                while True:
                    try:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=15.0, check=check)
                    except asyncio.TimeoutError:
                        await msg.clear_reactions()
                        embed.title = ''
                        embed.set_footer(text='{time_expired}')
                        await msg.edit(embed=ctx.localizer.format_embed(embed))
                        break

                    total = len(player.listeners)
                    votes = len(player.get_voters(func.__name__))

                    embed.description = f"{votes} out of {math.ceil(total*threshold/100)} required votes."
                    await msg.edit(embed=ctx.localizer.format_embed(embed))

                    if votes/total >= threshold/100:
                        player.clear_votes()
                        await msg.delete()
                        await func(self, ctx, *command_args, **kwargs)
                        break

            else:
                if votes != 0:
                    needed = math.ceil(total*threshold/100)
                    # TODO: redo this message to allow for other vote types
                    msg = ctx.localizer.format_str("{skip.require_vote}", _skips=votes, _total=needed)
                    await ctx.send(msg)

        return voteable_inner
    return make_voteable
