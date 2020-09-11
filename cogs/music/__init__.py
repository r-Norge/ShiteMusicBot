# Discord Packages
import lavalink
from discord.ext import commands

from ..utils import thumbnailer, timeformatter
from .music_errors import WrongTextChannelError


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("Music")

        self.bot = bot
        self.leave_timer.start()
        self.logger = self.bot.main_logger.bot_logger.getChild("Errors")
        bot.lavalink.add_event_hook(self.track_hook)

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        if textchannels := self.bot.settings.get(ctx.guild, 'channels.text', []):
            if ctx.channel.id not in textchannels:
                raise WrongTextChannelError('You need to be in the right text channel', channels=textchannels)
        return True

    async def cog_before_invoke(self, ctx):
        """ Ensures a valic player exists whenever a command is run """
        region = ctx.guild.region if isinstance(ctx.guild.region, str) else ctx.guild.region.value
        # Creates a new only if one doesn't exist, ensures a valid player for all checks.
        self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=region)

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)

    async def enqueue(self, ctx, track, embed):
        # TODO: rework
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        maxlength = self.max_track_length(ctx.guild, player)
        if maxlength and track['info']['length'] > maxlength:
            embed.description = ctx.localizer.format_str("{enqueue.toolong}",
                                                         _length=timeformatter.format_ms(track['info']['length']),
                                                         _max=timeformatter.format_ms(maxlength))
            return

        # TODO: make use of track vs track dict more consistent
        if isinstance(track, dict):
            thumbnail_url = await thumbnailer.ThumbNailer.identify(
                self, track['info']['identifier'], track['info']['uri'])
            track = lavalink.models.AudioTrack(track, ctx.author.id, thumbnail_url=thumbnail_url)

        track, pos_global, pos_local = player.add(requester=ctx.author.id, track=track)

        if player.current is not None:
            queue_duration = 0
            for i, track in enumerate(player.queue):
                if i == pos_global:
                    break
                queue_duration += int(track.duration)

            until_play = queue_duration + player.current.duration - player.position
            until_play = timeformatter.format_ms(until_play)
            embed.add_field(name="{enqueue.position}", value=f"`{pos_local + 1}({pos_global + 1})`", inline=True)
            embed.add_field(name="{enqueue.playing_in}", value=f"`{until_play} ({{enqueue.estimated}})`", inline=True)

        embed.title = '{enqueue.enqueued}'
        thumbnail_url = track.extra["thumbnail_url"]

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        duration = timeformatter.format_ms(int(track.duration))
        embed.description = f'[{track.title}]({track.uri})\n**{duration}**'

        return embed

    def max_track_length(self, guild, player):
        # TODO: Move somewhere else
        is_dynamic = self.bot.settings.get(guild, 'duration.is_dynamic', 'default_duration_type')
        maxlength = self.bot.settings.get(guild, 'duration.max', None)
        if maxlength is None:
            return None
        if len(player.listeners):  # Avoid division by 0.
            listeners = len(player.listeners)
        else:
            listeners = 1
        if maxlength > 10 and is_dynamic:
            return max(maxlength*60*1000/listeners, 60*10*1000)
        else:
            return maxlength*60*1000

    # commands
    from .basic_commands import (
        _boost, _disconnect, _djremove, _history, _lyrics, _move, _myqueue, _normalize, _now, _pause, _play, _queue,
        _reconnect, _remove, _scrub, _search, _seek, _shuffle, _skip, _skip_to, _stop, _user_queue_remove, _volume)
    # events
    from .events import check_leave_voice, cog_unload, leave_check, leave_timer, on_voice_state_update, track_hook


def setup(bot):
    bot.add_cog(Music(bot))
