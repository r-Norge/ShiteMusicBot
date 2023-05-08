import asyncio
import re
import urllib.parse as urlparse
from typing import List, Optional, Tuple

import discord
import lavalink
from discord import VoiceChannel
from discord.ext import commands, tasks
from lavalink.events import (
    NodeChangedEvent,
    NodeConnectedEvent,
    NodeDisconnectedEvent,
    PlayerUpdateEvent,
    QueueEndEvent,
    TrackEndEvent,
    TrackStartEvent,
    TrackStuckEvent,
)
from lavalink.models import AudioTrack

from bs4 import BeautifulSoup

from bot import MusicBot
from musicbot.utils import checks, timeformatter
from musicbot.utils.mixplayer.player import MixPlayer
from musicbot.utils.thumbnailer import Thumbnailer
from musicbot.utils.userinteraction.paginators import QueuePaginator, TextPaginator
from musicbot.utils.userinteraction.scroller import ClearMode, Scroller
from musicbot.utils.userinteraction.selector import (
    SelectMode,
    Selector,
    SelectorButton,
    SelectorItem,
    selector_button_callback,
)

from .decorators import require_playing, require_queue, require_voice_connection, voteable
from .music_errors import MusicError, PlayerNotAvailableError, WrongTextChannelError
from .voice_client import BasicVoiceClient

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


class Music(commands.Cog):
    def __init__(self, bot: MusicBot):
        self.bot: MusicBot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("Music")

        self.thumbnailer = Thumbnailer(bot=self.bot)

        self.leave_timer.start()
        if self.bot.lavalink is None:
            raise MusicError("Lavalink is not yet initialized")
        self.lavalink: lavalink.Client = self.bot.lavalink
        self.lavalink.add_event_hook(self.track_hook)

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        if textchannels := self.bot.settings.get(ctx.guild, 'channels.text', []):
            if ctx.channel.id not in textchannels:
                raise WrongTextChannelError('You need to be in the right text channel', channels=textchannels)
        return True

    async def cog_before_invoke(self, ctx):
        """Ensures a valid player exists whenever a command is run."""
        # Creates a new only if one doesn't exist, ensures a valid player for all checks.
        if ctx.guild:
            self.lavalink.player_manager.create(ctx.guild.id)

    def get_player(self, guild: discord.Guild) -> MixPlayer:
        player: Optional[MixPlayer] = self.lavalink.player_manager.get(guild.id)
        if player is None:
            raise PlayerNotAvailableError(f"Tried to get player for guild {guild.id} but got None")
        return player

    async def enqueue(self, ctx, track: AudioTrack, embed, standalone: bool = False,
                      check_max_length: bool = True) -> bool:
        player = self.get_player(ctx.guild)

        track_duration_str = timeformatter.format_track_duration(track)

        # Only add tracks that don't exceed the max track length
        maxlength = self.max_track_length(ctx.guild, player)
        if (track.stream or track.duration > maxlength) and check_max_length:
            embed.description = ctx.localizer.format_str("{enqueue.toolong}",
                                                         _length=track_duration_str,
                                                         _max=timeformatter.format_ms(maxlength))
            return False

        track.extra["thumbnail_url"] = await self.thumbnailer.identify(track.identifier, track.uri)
        track.requester = ctx.author.id

        # Add to player
        track, pos_global, pos_local = player.add(requester=ctx.author, track=track)

        if player.current is not None and not standalone:
            if player.current.stream:
                until_play = '--:--'
            else:
                until_play = player.queue_duration(include_current=True, end_pos=pos_global)
            embed.add_field(name="{enqueue.position}", value=f"`{pos_local + 1}({pos_global + 1})`", inline=True)
            embed.add_field(name="{enqueue.playing_in}", value=f"`{until_play} ({{enqueue.estimated}})`",
                            inline=True)

        embed.title = '{enqueue.enqueued}'

        if thumbnail_url := track.extra["thumbnail_url"]:
            embed.set_thumbnail(url=thumbnail_url)

        embed.description = f'[{track.title}]({track.uri})\n**{track_duration_str}**'
        return True

    def get_current_song_embed(self, ctx, include_time=False):
        player = self.get_player(ctx.guild)

        if not player.current:
            return

        song = f'**[{player.current.title}]({player.current.uri})**'
        if include_time:
            position = timeformatter.format_ms(player.position)
            duration = timeformatter.format_track_duration(player.current)
            song += f'\n({position}/{duration})'

        embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')

        if thumbnail_url := player.current.extra["thumbnail_url"]:
            embed.set_thumbnail(url=thumbnail_url)

        if member := ctx.guild.get_member(player.current.requester):
            embed.set_footer(text=f'{{requested_by}} {member.display_name}', icon_url=member.display_avatar.url)

        embed = ctx.localizer.format_embed(embed)
        return embed

    def max_track_length(self, guild, player) -> float:
        # Numeric constants
        minimum_dynamic_length = 10
        minutes_to_milliseconds = 60 * 1000
        configured_max = self.bot.settings.get(guild, 'duration.max', float('inf'))
        is_dynamic = self.bot.settings.get(guild, 'duration.is_dynamic', 'default_duration_type')
        listeners = max(1, len(player.listeners))  # Avoid division by 0

        if configured_max > minimum_dynamic_length and is_dynamic:
            return minutes_to_milliseconds * max(configured_max/listeners, minimum_dynamic_length)
        else:
            return minutes_to_milliseconds * configured_max

    async def _search_and_play_query(self, ctx, query: str, check_max_length: bool):
        self.logger.debug("Query: %s" % query)
        player = self.get_player(ctx.guild)
        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results: lavalink.LoadResult = await player.node.get_tracks(query)

        if not results or not results.tracks:
            return await ctx.send(ctx.localizer.format_str("{nothing_found}"))

        embed = discord.Embed(color=ctx.me.color)

        if results.load_type == 'PLAYLIST_LOADED':
            tracks = [track for track in results.tracks if
                      await self.enqueue(ctx, track, embed, True, check_max_length)]
            if tracks:
                embed.title = '{playlist_enqued}'
                embed.description = f'{results.playlist_info.name} - {len(tracks)} {{tracks}}'
            else:
                # TODO: This really means no tracks passed the max_length requirement
                return await ctx.send(ctx.localizer.format_str("{nothing_found}"))
        else:
            await self.enqueue(ctx, results.tracks[0], embed, check_max_length=check_max_length)

        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()

    @commands.command(name='play')
    @require_voice_connection(should_connect=True)
    async def _play(self, ctx, *, query: str):
        """Searches and plays a song from a given query."""
        await self._search_and_play_query(ctx, query, check_max_length=True)

    @commands.command(name='forceplay')
    @require_voice_connection(should_connect=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _forceplay(self, ctx, *, query: str):
        """Searches and plays a song from a given query, ignoring configured max duration."""
        await self._search_and_play_query(ctx, query, check_max_length=False)

    @commands.command(name='seek')
    @checks.dj_or(alone=True, track_requester=True)
    @require_voice_connection()
    @require_playing(require_user_listening=True)
    async def _seek(self, ctx, *, time: str):
        """Seeks to a given position in a track."""
        player = self.get_player(ctx.guild)
        if seconds := time_rx.search(time):
            # Convert to milliseconds, include sign
            milliseconds = int(seconds.group())*1000 * (-1 if time.startswith('-1') else 1)

            track_time = player.position + milliseconds
            await player.seek(int(track_time))
            msg = ctx.localizer.format_str("{seek.track_moved}", _position=timeformatter.format_ms(track_time))
            await ctx.send(msg)
        else:
            await ctx.send(ctx.localizer.format_str("{seek.missing_amount}"))

    @commands.command(name='skip')
    @require_voice_connection()
    @require_playing()
    @voteable(requester_override=True, react_to_vote=True)
    async def _skip(self, ctx):
        """Skips the current track."""
        player = self.get_player(ctx.guild)

        await player.skip()
        embed = self.get_current_song_embed(ctx)
        await ctx.send(ctx.localizer.format_str("{skip.skipped}"), embed=embed)

    @commands.command(name='skipto')
    @checks.dj_or(alone=True)
    @require_playing(require_user_listening=True)
    async def _skip_to(self, ctx, pos: int = 1):
        """Plays the queue from a specific point. Disregards tracks before the pos."""
        player = self.get_player(ctx.guild)

        # TODO: Do all queue out of range messages the same way
        if pos < 1:
            return await ctx.send(ctx.localizer.format_str("{skip_to.invalid_pos}"))
        if len(player.queue) < pos:
            return await ctx.send(ctx.localizer.format_str("{skip_to.exceeds_queue}"))

        await player.skip(pos - 1)

        if player.current:
            msg = ctx.localizer.format_str("{skip_to.skipped_to}", _title=player.current.title, _pos=pos)
            await ctx.send(msg)
        else:
            self.logger.error("Expected current track to be valid due to bounds checks")

    @commands.command(name='stop')
    @require_voice_connection()
    @require_playing(require_user_listening=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _stop(self, ctx):
        """Stops the player and clears its queue."""
        player = self.get_player(ctx.guild)
        player.queue.clear()
        await player.stop()

        embed = discord.Embed(color=ctx.me.color, title='{stop}')
        await ctx.send(embed=ctx.localizer.format_embed(embed))

    @commands.command(name='now')
    @require_playing()
    async def _now(self, ctx):
        if embed := self.get_current_song_embed(ctx, include_time=True):
            embed = ctx.localizer.format_embed(embed)
            await ctx.send(embed=embed)

    @commands.command(name='queue')
    @require_queue(require_member_queue=True)
    async def _queue(self, ctx, *, member: Optional[discord.Member] = None):
        """Shows the player's queue."""
        player = self.get_player(ctx.guild)
        pagified_queue = QueuePaginator(ctx.localizer, player, color=ctx.me.color, member=member)
        scroller = Scroller(ctx, pagified_queue)
        await scroller.start_scrolling(ClearMode.ManualExit | ClearMode.Timeout)

    @commands.command(name='myqueue')
    @require_queue(require_author_queue=True)
    async def _myqueue(self, ctx):
        """Shows your queue."""
        await self._queue(ctx, member=ctx.author)

    @commands.command(name='pause')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    @require_playing()
    async def _pause(self, ctx):
        """Pauses/Resumes the current track."""
        player = self.get_player(ctx.guild)
        await player.set_pause(not player.paused)
        if player.paused:
            await ctx.send(ctx.localizer.format_str("{resume.paused}"))
        else:
            await ctx.send(ctx.localizer.format_str("{resume.resumed}"))

    @commands.command(name='shuffle')
    @require_voice_connection()
    @require_queue(require_author_queue=True)
    async def _shuffle(self, ctx):
        """Shuffles your queue."""
        player = self.get_player(ctx.guild)
        player.shuffle_user_queue(ctx.author)
        await ctx.send(ctx.localizer.format_str("{shuffle}"))

    @commands.command(name='move')
    @require_voice_connection()
    @require_queue(require_author_queue=True)
    async def _move(self, ctx):
        """Moves a song in your queue."""
        player = self.get_player(ctx.guild)

        # We create a new selector for each selection
        def build_move_selector(ctx, queue: List[AudioTrack], title: str, first: bool):
            @selector_button_callback
            async def return_track(_interaction, _button, track):
                return track

            choices = []
            for index, track in enumerate(queue, start=1):
                blank = " " * 6
                if first:
                    prefix = f'`{blank}`\n`{index:<6}`'
                else:
                    prefix = f'`{index:<3}-> `\n`{blank}`'
                label = f'{prefix} [{track.title}]({track.uri})'
                selection = SelectorItem(label, str(index), return_track(track))
                choices.append(selection)

            return Selector(ctx, choices, select_mode=SelectMode.SpanningMultiSelect, use_tick_for_stop_emoji=True,
                            color=ctx.me.color, title=ctx.localizer.format_str(title))

        message = None
        page = 0
        while True:
            # Prompt the user for which track to move
            selector = build_move_selector(ctx, player.user_queue(ctx.author), "{moved.choose_pos}", True)
            message, timed_out, track_to_move = await selector.start_scrolling(ClearMode.Timeout, message, page)
            page = selector.page_number

            if not track_to_move or timed_out:
                break

            # Prompt the user for where to move it
            selector = build_move_selector(ctx, player.user_queue(ctx.author), "{moved.choose_song}", False)
            message, timed_out, track_to_replace = await selector.start_scrolling(ClearMode.Timeout, message, page)
            page = selector.page_number

            if not track_to_replace or timed_out:
                break

            # At this point the user has chosen two songs, we will move the first song to be in front of the second
            # one in the queue. Find the index of both songs in the current queue

            # Keep updating the user queue in case it changes while the user is selecting songs
            user_queue = player.user_queue(ctx.author)
            try:
                pos_initial = user_queue.index(track_to_move[0])
                pos_final = user_queue.index(track_to_replace[0])
                player.move_user_track(ctx.author, pos_initial, pos_final)
            except ValueError:
                # Track not found in queue. Queue could have changed during selection
                # if a song was skipped or the current song finished
                pass

        if message:
            await message.delete()

    async def _interactive_remove(self, ctx, queue: List[AudioTrack]):
        """Helper function for creating an interactive selector over a given queue
        in which will remove the selected tracks on exit.
        """
        player = self.get_player(ctx.guild)

        tracks_to_remove = []

        @selector_button_callback
        async def update_remove_list(_interaction, button: SelectorButton, tracks_list, track: AudioTrack):
            # It seems duplicate songs still don't satisfy equality
            # which means remove is sufficient to preserve order
            # of similar items
            if track in tracks_list:
                tracks_list.remove(track)
            else:
                tracks_list.append(track)

            if button.style == discord.ButtonStyle.red:
                button.style = discord.ButtonStyle.gray
            else:
                button.style = discord.ButtonStyle.red

        selector_buttons = []
        # Build each selection from the queue, a visible string and a callback.
        for index, track in enumerate(queue, start=1):
            requester = self.bot.get_user(track.requester)
            selector_buttons.append(
                SelectorItem(f'`{index}` [{track.title}]({track.uri}) - {requester.mention if requester else ""}',
                             str(index), update_remove_list(tracks_to_remove, track)))

        remove_selector = Selector(ctx, selector_buttons, select_mode=SelectMode.MultiSelect,
                                   use_tick_for_stop_emoji=True, color=ctx.me.color, title='Select songs to remove')
        _, timed_out, _ = await remove_selector.start_scrolling(ClearMode.AnyExit)

        # If any tracks were removed create a scroller for navigating them
        if tracks_to_remove and not timed_out:
            paginator = TextPaginator(color=ctx.me.color, title="Removed")

            tracks_removed: List[Tuple[int, str]] = []
            for track in tracks_to_remove:
                if remove_result := player.remove_track(track):
                    (position, removed_track) = remove_result
                    if requester := self.bot.get_user(removed_track.requester):
                        tracks_removed.append((position, f"{removed_track.title} - {requester.mention}"))

            # remove_track returns the global queue index of the track,
            # so we display the removed tracks in "queue order"
            for removed in sorted(tracks_removed, key=lambda x: x[0]):
                paginator.add_line(removed[1])

            paginator.close_page()
            scroller = Scroller(ctx, paginator)
            await scroller.start_scrolling(ClearMode.ManualExit | ClearMode.Timeout)

    @commands.command(name='remove')
    @require_voice_connection()
    @require_queue(require_author_queue=True)
    async def _remove(self, ctx):
        """Remove a song from your queue."""
        player = self.get_player(ctx.guild)
        return await self._interactive_remove(ctx, player.user_queue(ctx.author))

    @commands.command(name="DJremove")
    @checks.dj_or()
    @require_voice_connection()
    @require_queue()
    async def _djremove(self, ctx, member: Optional[discord.Member] = None):
        """Remove a song from either the global queue or a users queue."""
        player = self.get_player(ctx.guild)
        # TODO: add way to allow "member" as regular arg in require_queue() instead of only kwargs
        queue = player.user_queue(member) if member else player.global_queue()
        return await self._interactive_remove(ctx, queue)

    @commands.command(name='removeuser')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    @require_queue(require_member_queue=True)
    async def _user_queue_remove(self, ctx, *, member: discord.Member):
        """Remove a song from either the global queue or a users queue."""
        player = self.get_player(ctx.guild)
        player.remove_user_queue(member)

        embed = discord.Embed(description="{dj_remove_user}", color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed, _id=member.id)

        await ctx.send(embed=embed)

    @commands.command(name='search')
    @require_voice_connection(should_connect=True)
    async def _search(self, ctx, *, query):
        player = self.get_player(ctx.guild)

        self.logger.debug("Query: %s" % query)
        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            embed = discord.Embed(description='{nothing_found}', color=0x36393F)
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)

        def make_enqueue_callback(func, *args):
            """Take a callback and convert it to the form required by a SelectorItem."""
            async def inner(_interaction, _button):
                return await func(*args)
            return inner

        # This is the base embed that will be modified by the selector
        embed = discord.Embed(color=ctx.me.color)
        buttons = []
        for i, track in enumerate(results['tracks'], start=1):
            duration = timeformatter.format_ms(int(track.duration))
            interaction = SelectorItem(f'`{i}` [{track.title}]({track.uri}) `{duration}`', str(i),
                                       make_enqueue_callback(self.enqueue, ctx, track, embed))
            buttons.append(interaction)

        search_selector = Selector(ctx, buttons, select_mode=SelectMode.SingleSelect,
                                   color=ctx.me.color, title=ctx.localizer.format_str('{results}'))
        message, timed_out, _ = await search_selector.start_scrolling(ClearMode.Timeout)

        if timed_out:
            return

        await message.edit(embed=ctx.localizer.format_embed(embed), view=None)

        if not player.is_playing:
            await player.play()

    @commands.command(name='disconnect')
    @require_voice_connection()
    @voteable(DJ_override=True, react_to_vote=True)
    async def _disconnect(self, ctx):
        """Disconnects the player from the voice channel and clears its queue."""
        player = self.get_player(ctx.guild)

        player.queue.clear()
        await player.stop()
        await ctx.voice_client.disconnect()
        embed = discord.Embed(description='{disconnect.disconnected}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='reconnect')
    @require_voice_connection()
    @voteable(DJ_override=True, react_to_vote=True)
    async def _reconnect(self, ctx):
        """Tries to disconnect then reconnect the player in case the bot gets stuck on a song."""
        player = self.get_player(ctx.guild)
        current_channel = player.channel_id

        async def inner_reconnect():
            await player.stop()
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                await asyncio.sleep(1)  # Pretend stuff is happening/give everything some time to reset.
                channel = ctx.guild.get_channel(current_channel)
                await channel.connect(cls=BasicVoiceClient)

        if player.current:
            track = player.current
            start_time = player.position
            await inner_reconnect()
            if track:
                await player.play(track, start_time=int(start_time))
        else:
            await inner_reconnect()

    @commands.command(name='volume')
    @checks.dj_or(alone=True, track_requester=True)
    @require_playing(require_user_listening=True)
    async def _volume(self, ctx, volume: Optional[int] = None):
        """Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink."""
        player = self.get_player(ctx.guild)

        if not volume:
            return await ctx.send(f'🔈 | {player.volume}%')

        is_dj = checks.is_dj(ctx)
        is_admin = getattr(ctx.author.guild_permissions, 'administrator', None) is True
        if player.current and (int(player.current.requester) == ctx.author.id and not is_dj and not is_admin):
            if not 50 <= volume <= 125:
                return await ctx.send(ctx.localizer.format_str("{volume.out_of_range}"))
        await player.set_volume(volume)

        embed = discord.Embed(description="{volume.set_to}", color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed, _volume=player.volume)
        await ctx.send(embed=embed)

    @commands.command(name='forcedisconnect')
    @checks.dj_or(alone=True)
    async def _forcedisconnect(self, ctx):
        """Attempts to force disconnect the bot without checking if it is connected initially."""
        try:
            player = self.get_player(ctx.guild)
            player.queue.clear()
            await player.stop()
        except Exception as e:
            self.logger.error("Error forcedisconnecting")
            self.logger.exception(e)
        await ctx.voice_client.disconnect(force=True)
        embed = discord.Embed(description='{disconnect.disconnected}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='normalize')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    async def _normalize(self, ctx):
        """Reset the equalizer and volume."""
        player = self.get_player(ctx.guild)

        await player.set_volume(100)
        await player.bassboost(False)
        await player.nightcoreify(False)

        embed = discord.Embed(description='{volume.reset}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='boost')
    @checks.dj_or(alone=True)
    async def _boost(self, ctx, boost: bool = False):
        """Set the equalizer to bass boost the music."""
        player = self.get_player(ctx.guild)

        if boost is not None:
            await player.bassboost(boost)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = '{boost.on}' if player.boosted else '{boost.off}'

        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='nightcore')
    @checks.dj_or(alone=True)
    async def _nightcore(self, ctx, boost: bool = False):
        """Set a filter mimicking nightcore the music."""
        player = self.get_player(ctx.guild)

        await player.nightcoreify(boost)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = '{nightcore.on}' if player.nightcore_enabled else '{nightcore.off}'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='history')
    async def _history(self, ctx):
        """Show the last 10 songs played."""
        player = self.get_player(ctx.guild)
        history = player.get_history()
        if not history:
            embed = discord.Embed(description='{history.empty}', color=ctx.me.color)
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)
        track = history[0]
        description = ctx.localizer.format_str("{history.current}", _title=track.title, _uri=track.uri,
                                               _id=track.requester) + '\n\n'
        description += ctx.localizer.format_str("{history.previous}", _len=len(history)-1) + '\n'
        for index, track in enumerate(history[1:], start=1):
            description += ctx.localizer.format_str("{history.track}", _index=-index, _title=track.title,
                                                    _uri=track.uri, _id=track.requester) + '\n'

        embed = discord.Embed(title=ctx.localizer.format_str('{history.title}'), color=ctx.me.color,
                              description=description)

        if current := player.current:
            if thumbnail_url := current.extra["thumbnail_url"]:
                embed.set_thumbnail(url=thumbnail_url)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.command(name='lyrics')
    async def _lyrics(self, ctx, *query: str):
        """Search for lyrics of a song."""
        # Check for API key
        if not (genius_access_token := self.bot.APIkeys.get('genius')):
            return await ctx.send(ctx.localizer.format_str('{errors.missing_api_key}'))

        # Extract all arguments into a single string
        query = ' '.join(query)

        # If no query is given, use the current playing song
        if not query:
            player = self.get_player(ctx.guild)
            if not player.is_playing:
                return await ctx.send(ctx.localizer.format_str('{nothing_playing}'))
            query = player.current.title

        # Filter out unwanted words to improve chances of finding the correct song
        stopwords = ['music', 'video', 'version', 'original', 'lyrics', 'lyric',
                     'official', 'live', 'instrumental', 'audio', 'hd']
        query = ' '.join([word for word in query.split() if word.lower() not in stopwords])

        # Send a message to indicate that the bot is searching for the lyrics
        # Unfortunately, the Genius API does not provide the lyrics directly, so we have to scrape the website
        # This is a bit slow, so we send a message to indicate that the bot is searching
        embed = discord.Embed(description=':mag_right:')
        status_msg = await ctx.send(embed=embed)

        # Define an internal function to make requests to the Genius API
        async def get_site_content(url: str, scrape: bool = False) -> Optional[dict | str]:
            header = {} if scrape else {'Authorization': f'Bearer {genius_access_token}'}
            async with self.bot.session.get(url, headers=header) as r:
                if r.status != 200:
                    embed = discord.Embed(description=ctx.localizer.format_str('{errors.error_occurred}'),
                                          color=0xFF0000)
                    await status_msg.edit(embed=embed)
                    return
                if scrape:
                    return await r.text()
                return await r.json()

        # Query the song
        url = 'https://api.genius.com/search?' + urlparse.urlencode({'q': query})
        response = await get_site_content(url)
        if not response:
            return

        # Select top song result
        try:
            song = {}
            for hit in response['response']['hits']:
                if hit['type'] == 'song':
                    song = hit['result']
                    break
            song_url = song['url']
        except KeyError:
            embed = discord.Embed(description=ctx.localizer.format_str('{nothing_found}'), color=0xFF0000)
            return await status_msg.edit(embed=embed)

        # Scrape the lyrics from the song page
        response = await get_site_content(song_url, scrape=True)
        if not response:
            return

        # Find the lyrics in our scraped data
        scraped_data = BeautifulSoup(response, 'html.parser')
        lyrics = scraped_data.findAll('div')
        for div in lyrics:
            if div.has_attr('data-lyrics-container'):
                lyrics_div = div
                break  # We found the lyrics, so we can stop searching

        # Replace <br> tags with newlines and remove HTML tags
        # This is a bit hacky, but it works
        lyrics = re.sub(r'<br\s*/>', '\n', str(lyrics_div))
        lyrics = re.sub(r'<\/*\w+.*>', '', lyrics)

        # Construct the output embed
        paginator = TextPaginator(max_size=2000, max_lines=50, color=0xFFFF64)
        for line in lyrics.split('\n'):
            paginator.add_line(line)

        # Set metadata on the first page
        paginator.pages[0].url = song_url
        paginator.pages[0].title = song.get('full_title', '*?*')
        paginator.pages[0].set_thumbnail(url=song.get('header_image_thumbnail_url', 'https://i.imgur.com/NmCTsoF.png'))
        paginator.pages[0].set_author(name='Genius', icon_url='https://i.imgur.com/NmCTsoF.png')

        # Send the output
        if len(paginator.pages) < 4:
            for page in paginator.pages:
                await ctx.send(embed=page)
        else:
            paginator.add_page_indicator(ctx.localizer)
            await Scroller(ctx, paginator).start_scrolling(ClearMode.AnyExit)

        # Since we are using a paginator, we need to delete the status message
        # because the final output may consist of multiple pages
        await status_msg.delete()

    @commands.command(name='scrub')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    @require_playing(require_user_listening=True)
    async def _scrub(self, ctx):
        """Shows a set of controls which can be used to skip forward or backwards in the song."""
        player = self.get_player(ctx.guild)
        controls = '{scrub.controls}'

        @selector_button_callback
        async def seek(_interacton, _button, seconds):
            newpos = player.position + seconds * 1000
            return await player.seek(newpos)

        @selector_button_callback
        async def toggle_pause(_interaction, button: SelectorButton):
            should_pause = not player.paused
            button.style = discord.ButtonStyle.red if should_pause else discord.ButtonStyle.gray
            return await player.set_pause(should_pause)

        scrubber_controls = [
            SelectorItem("", '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', seek(-1000)),
            SelectorItem("", '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}', seek(-15)),
            SelectorItem("", '\N{Black Right-Pointing Triangle with Double Vertical Bar}', toggle_pause()),
            SelectorItem("", '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}', seek(15)),
            SelectorItem("", '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', seek(1000))
        ]
        scrubber = Selector(ctx, scrubber_controls, select_mode=SelectMode.MultiSelect, use_tick_for_stop_emoji=True,
                            default_text=ctx.localizer.format_str(controls), color=ctx.me.color)
        await scrubber.start_scrolling(ClearMode.AnyExit)

    @commands.group(name='loop')
    async def _loop(self, ctx):
        # This is done using subcommands to have separate vote counts for starting and stopping.
        if ctx.invoked_subcommand is None:
            player = self.get_player(ctx.guild)
            embed = discord.Embed(color=ctx.me.color, title='Loop status')

            if player.looping:
                embed.description = 'The bot is currently looping: ♾️'
            else:
                embed.description = 'The bot is currently not looping'
            await ctx.send(embed=embed)

    @_loop.command(name='start')
    @require_playing(require_user_listening=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _loop_start(self, ctx):
        """Set the equalizer to bass boost the music."""
        player = self.get_player(ctx.guild)
        player.enable_looping(True)
        embed = discord.Embed(color=ctx.me.color)
        embed.description = 'Looping turned on'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @_loop.command(name='stop')
    @require_playing(require_user_listening=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _loop_stop(self, ctx):
        """Set the equalizer to bass boost the music."""
        player = self.get_player(ctx.guild)
        player.enable_looping(False)
        embed = discord.Embed(color=ctx.me.color)
        embed.description = 'Looping turned off'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    async def cog_unload(self):
        self.lavalink._event_hooks.clear()

    async def track_hook(self, event):
        if isinstance(event, TrackEndEvent):
            if channel := self.bot.get_channel(event.player.fetch('channel')):
                if isinstance(channel, VoiceChannel):
                    player = self.get_player(channel.guild)
                    player.skip_voters.clear()

        if isinstance(event, TrackStartEvent):
            pass
        if isinstance(event, QueueEndEvent):
            if channel := self.bot.get_channel(event.player.fetch('channel')):
                if isinstance(channel, VoiceChannel):
                    await self.check_leave_voice(channel.guild)
        if isinstance(event, PlayerUpdateEvent):
            pass
        if isinstance(event, NodeDisconnectedEvent):
            pass
        if isinstance(event, NodeConnectedEvent):
            pass
        if isinstance(event, NodeChangedEvent):
            pass
        if isinstance(event, TrackStuckEvent):
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, _: discord.VoiceState, after: discord.VoiceState):
        """Updates listeners when the bot or a user changes voice state."""
        if self.bot.user is None:
            return  # Bot not logged in
        if member.id == self.bot.user.id and after.channel is not None:
            voice_channel = after.channel
            try:
                player = self.get_player(member.guild)
            except PlayerNotAvailableError:  # This is expected if we have not created a player for the guild yet
                return
            player.clear_listeners()
            for member in voice_channel.members:
                if not member.bot:
                    player.update_listeners(member, member.voice)

        if not member.bot:
            try:
                player = self.get_player(member.guild)
            except PlayerNotAvailableError:  # This is expected if we have not created a player for the guild yet
                return
            player.update_listeners(member, after)
            await self.check_leave_voice(member.guild)

    async def check_leave_voice(self, guild: discord.Guild):
        """Checks if the bot should leave the voice channel."""
        # TODO, disconnect timer?
        player = self.get_player(guild)
        if len(player.listeners) == 0 and player.is_connected:
            if player.queue.empty and player.current is None:
                await player.stop()
                if voice_client := guild.voice_client:
                    await voice_client.disconnect(force=False)

    async def leave_check(self):
        for player_id in self.lavalink.player_manager.players:
            if guild := self.bot.get_guild(player_id):
                await self.check_leave_voice(guild)

    @tasks.loop(seconds=10.0)
    async def leave_timer(self):
        try:
            await self.leave_check()
        except Exception as err:
            self.logger.error("Error in leave_timer loop")
            self.logger.exception(err)


async def setup(bot):
    await bot.add_cog(Music(bot))
