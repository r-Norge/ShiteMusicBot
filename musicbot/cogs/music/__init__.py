# Discord Packages
import discord
from discord.ext import commands, tasks
from lavalink.events import (
    NodeChangedEvent, NodeConnectedEvent, NodeDisconnectedEvent, PlayerUpdateEvent, QueueEndEvent, TrackEndEvent,
    TrackStartEvent, TrackStuckEvent)
from lavalink.models import AudioTrack

import asyncio
import json
import re
import urllib
from typing import List

from bs4 import BeautifulSoup

# Bot Utilities
from musicbot.utils.mixplayer.player import MixPlayer
from ...utils import checks, thumbnailer, timeformatter
from ...utils.userinteraction.paginators import QueuePaginator, TextPaginator
from ...utils.userinteraction.scroller import ClearOn, Scroller
from ...utils.userinteraction.selector import SelectMode, Selector, SelectorButton, SelectorItem
from .decorators import BasicVoiceClient, require_playing, require_queue, require_voice_connection, voteable
from .music_errors import WrongTextChannelError

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("Music")

        self.bot = bot
        self.leave_timer.start()
        self.bot.lavalink.add_event_hook(self.track_hook)

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        if textchannels := self.bot.settings.get(ctx.guild, 'channels.text', []):
            if ctx.channel.id not in textchannels:
                raise WrongTextChannelError('You need to be in the right text channel', channels=textchannels)
        return True

    async def cog_before_invoke(self, ctx):
        """ Ensures a valid player exists whenever a command is run """
        # Creates a new only if one doesn't exist, ensures a valid player for all checks.
        self.bot.lavalink.player_manager.create(ctx.guild.id)

    async def enqueue(self, ctx, track, embed, silent=False, check_max_length=True) -> tuple[discord.Embed, bool]:
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        # Only add tracks that don't exceed the max track length
        if maxlength := self.max_track_length(ctx.guild, player):
            if track.duration > maxlength and check_max_length:
                if track.stream:
                    length = '{live}'
                else:
                    length = timeformatter.format_ms(track.duration)
                embed.description = ctx.localizer.format_str("{enqueue.toolong}",
                                                             _length=length,
                                                             _max=timeformatter.format_ms(maxlength))
                return embed, False

        track.extra["thumbnail_url"] = await thumbnailer.ThumbNailer.identify(self, track.identifier, track.uri)
        track.requester = ctx.author.id

        # Add to player
        track, pos_global, pos_local = player.add(requester=ctx.author.id, track=track)

        if player.current is not None and not silent:
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

        if track.stream:
            duration = '{live}'
        else:
            duration = timeformatter.format_ms(int(track.duration))
        embed.description = f'[{track.title}]({track.uri})\n**{duration}**'

        return embed, True

    def get_current_song_embed(self, ctx, include_time=False):
        player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.current:
            return

        song = f'**[{player.current.title}]({player.current.uri})**'
        if include_time:
            position = timeformatter.format_ms(player.position)
            if player.current.stream:
                duration = '{live}'
            else:
                duration = timeformatter.format_ms(player.current.duration)
            song += f'\n({position}/{duration})'

        embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')

        if thumbnail_url := player.current.extra["thumbnail_url"]:
            embed.set_thumbnail(url=thumbnail_url)

        if member := ctx.guild.get_member(player.current.requester):
            embed.set_footer(text=f'{{requested_by}} {member.display_name}', icon_url=member.display_avatar.url)

        embed = ctx.localizer.format_embed(embed)
        return embed

    def max_track_length(self, guild, player):
        if maxlength := self.bot.settings.get(guild, 'duration.max', None):
            is_dynamic = self.bot.settings.get(guild, 'duration.is_dynamic', 'default_duration_type')
            listeners = max(1, len(player.listeners))  # Avoid division by 0

            if maxlength > 10 and is_dynamic:
                return max(maxlength*60*1000/listeners, 60*10*1000)
            else:
                return maxlength*60*1000
        else:
            return None

    @commands.command(name='play')
    @require_voice_connection(should_connect=True)
    async def _play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        self.logger.debug("Query: %s" % query)
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

        if not results or not results.tracks:
            return await ctx.send(ctx.localizer.format_str("{nothing_found}"))

        embed = discord.Embed(color=ctx.me.color)

        if results.load_type == 'PLAYLIST_LOADED':
            numtracks = 0
            for track in results.tracks:
                _, track_added = await self.enqueue(ctx, track, embed, silent=True)
                if track_added:
                    numtracks += 1

            embed.title = '{playlist_enqued}'
            embed.description = f'{results.playlist_info.name} - {numtracks} {{tracks}}'
        else:
            track = results.tracks[0]
            await self.enqueue(ctx, track, embed)

        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()

    @commands.command(name='seek')
    @checks.dj_or(alone=True, track_requester=True)
    @require_voice_connection()
    @require_playing(require_user_listening=True)
    async def _seek(self, ctx, *, time: str):
        """ Seeks to a given position in a track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if seconds := time_rx.search(time):
            # Convert to milliseconds, include sign
            milliseconds = int(seconds.group())*1000 * (-1 if time.startswith('-1') else 1)

            track_time = player.position + milliseconds
            await player.seek(track_time)
            msg = ctx.localizer.format_str("{seek.track_moved}", _position=timeformatter.format_ms(track_time))
            await ctx.send(msg)
        else:
            await ctx.send(ctx.localizer.format_str("{seek.missing_amount}"))

    @commands.command(name='skip')
    @require_voice_connection()
    @require_playing()
    @voteable(requester_override=True, react_to_vote=True)
    async def _skip(self, ctx):
        """ Skips the current track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.skip()
        embed = self.get_current_song_embed(ctx)
        await ctx.send(ctx.localizer.format_str("{skip.skipped}"), embed=embed)

    @commands.command(name='skipto')
    @checks.dj_or(alone=True)
    @require_playing(require_user_listening=True)
    async def _skip_to(self, ctx, pos: int = 1):
        """ Plays the queue from a specific point. Disregards tracks before the pos. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        # TODO: Do all queue out of range messages the same way
        if pos < 1:
            return await ctx.send(ctx.localizer.format_str("{skip_to.invalid_pos}"))
        if len(player.queue) < pos:
            return await ctx.send(ctx.localizer.format_str("{skip_to.exceeds_queue}"))

        await player.skip(pos - 1)

        msg = ctx.localizer.format_str("{skip_to.skipped_to}", _title=player.current.title, _pos=pos)
        await ctx.send(msg)

    @commands.command(name='stop')
    @require_voice_connection()
    @require_playing(require_user_listening=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _stop(self, ctx):
        """ Stops the player and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
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
    async def _queue(self, ctx, *, member: discord.Member = None):
        """ Shows the player's queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        pagified_queue = QueuePaginator(ctx.localizer, player, color=ctx.me.color, member=member)
        scroller = Scroller(ctx, pagified_queue)
        await scroller.start_scrolling(ClearOn.ManualExit | ClearOn.Timeout)

    @commands.command(name='myqueue')
    @require_queue(require_author_queue=True)
    async def _myqueue(self, ctx):
        """ Shows your queue. """
        await self._queue(ctx, member=ctx.author)

    @commands.command(name='pause')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    @require_playing()
    async def _pause(self, ctx):
        """ Pauses/Resumes the current track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        await player.set_pause(not player.paused)
        if player.paused:
            await ctx.send(ctx.localizer.format_str("{resume.paused}"))
        else:
            await ctx.send(ctx.localizer.format_str("{resume.resumed}"))

    @commands.command(name='shuffle')
    @require_voice_connection()
    @require_queue(require_author_queue=True)
    async def _shuffle(self, ctx):
        """ Shuffles your queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.shuffle_user_queue(ctx.author.id)
        await ctx.send(ctx.localizer.format_str("{shuffle}"))

    @commands.command(name='move')
    @require_voice_connection()
    @require_queue(require_author_queue=True)
    async def _move(self, ctx):
        """ Moves a song in your queue. """
        player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        # We create a new selector for each selection
        def move_selector(ctx, queue: List[AudioTrack], title: str, first: bool):
            async def return_track(track):
                return track

            choices = []
            for index, track in enumerate(queue, start=1):
                blank = " " * 6
                if first:
                    prefix = f'`{blank}`\n`{index:<6}`'
                else:
                    prefix = f'`{index:<3}-> `\n`{blank}`'
                label = f'{prefix} [{track.title}]({track.uri})'
                selection = SelectorItem(label, str(index), wrap_in_button_callback(return_track, track))
                choices.append(selection)

            return Selector(ctx, choices, select_mode=SelectMode.SpanningMultiSelect, use_tick_for_stop_emoji=True,
                            color=ctx.me.color, title=ctx.localizer.format_str(title))

        message = None
        page = 0
        while True:
            # Prompt the user for which track to move
            selector = move_selector(ctx, player.user_queue(ctx.author.id), "{moved.choose_pos}", True)
            message, track_to_move = await selector.start_scrolling(ClearOn.Timeout, message, page)
            page = selector.page_number

            if not track_to_move:
                break

            # Prompt the user for where to move it
            selector = move_selector(ctx, player.user_queue(ctx.author.id), "{moved.choose_song}", False)
            message, track_to_replace = await selector.start_scrolling(ClearOn.Timeout, message, page)
            page = selector.page_number

            if not track_to_replace:
                break

            # At this point the user has chosen two songs, we will move the first song to be in front of the second
            # one in the queue. Find the index of both songs in the current queue

            # Keep updating the user queue in case it changes while the user is selecting songs
            user_queue = player.user_queue(ctx.author.id)
            try:
                pos_initial = user_queue.index(track_to_move[0])
                pos_final = user_queue.index(track_to_replace[0])
                player.move_user_track(ctx.author.id, pos_initial, pos_final)
            except ValueError:
                # Track not found in queue. Queue could have changed during selection
                # if a song was skipped or the current song finished
                pass

        if message:
            await message.delete()

    @commands.command(name='remove')
    @require_voice_connection()
    @require_queue(require_author_queue=True)
    async def _remove(self, ctx):
        player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        user_queue: List[AudioTrack] = player.user_queue(ctx.author.id)

        tracks_to_remove = []

        async def update_remove_list(tracks_list, track):
            if track in tracks_list:
                tracks_list.remove(track)
            else:
                tracks_list.append(track)

        # The callback from the selector takes a discord interaction and
        # the button class. We wrap the track remove callback to handle those
        # arguments and update button color
        def add_change_button_color(func, *args):
            async def inner(_, button: SelectorButton):
                if button.style == discord.ButtonStyle.red:
                    button.style = discord.ButtonStyle.gray
                else:
                    button.style = discord.ButtonStyle.red
                return await func(*args)
            return inner

        selector_buttons = []
        for index, track in enumerate(user_queue, start=1):
            selector_buttons.append(
                SelectorItem(f'`{index}` [{track.title}]({track.uri})', str(index),
                             add_change_button_color(update_remove_list, tracks_to_remove, track)))

        remove_selector = Selector(ctx, selector_buttons, select_mode=SelectMode.MultiSelect,
                                   use_tick_for_stop_emoji=True, color=ctx.me.color, title='Select songs to remove')
        await remove_selector.start_scrolling(ClearOn.AnyExit)

        # If any tracks were removed create a scroller for navigating them
        if tracks_to_remove:
            paginator = TextPaginator(color=ctx.me.color, title="Removed")

            # If the user spent a long time selecting songs the queue might have changed
            user_queue = player.user_queue(ctx.author.id)
            track_indexes_to_remove = [i for i, track in enumerate(user_queue) if track in tracks_to_remove]

            # Sort in reverse order since songs shift index when deleting
            tracks_removed = []
            for track in sorted(track_indexes_to_remove, reverse=True):
                if removed_track := player.remove_user_track(ctx.author.id, track):
                    tracks_removed.append(f"{removed_track.title}")

            # We want to display the removed tracks in the original queue order, so reverse the list once again
            for removed in reversed(tracks_removed):
                paginator.add_line(removed)

            paginator.close_page()
            scroller = Scroller(ctx, paginator)
            await scroller.start_scrolling(ClearOn.ManualExit | ClearOn.Timeout)

    @commands.command(name="DJremove")
    @checks.dj_or()
    @require_voice_connection()
    @require_queue()
    async def _djremove(self, ctx, pos: int, member: discord.Member = None):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        # TODO: add way to allow "member" as regular arg in require_queue() instead of only kwargs
        queue = player.user_queue(member.id) if member else player.queue

        # TODO: Do all queue out of range messages the same way
        if pos <= len(queue) and pos >= 1:
            if member is None:
                removed = player.remove_global_track(pos - 1)
            else:
                removed = player.remove_user_track(member.id, pos - 1)

            requester = self.bot.get_user(removed.requester)
            await ctx.send(ctx.localizer.format_str("{dj_removed}", _title=removed.title, _user=requester.display_name))
        else:
            await ctx.send(ctx.localizer.format_str("{out_of_range}", _len=len(queue)))

    @commands.command(name='removeuser')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    @require_queue(require_member_queue=True)
    async def _user_queue_remove(self, ctx, *, member: discord.Member):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.remove_user_queue(member.id)

        embed = discord.Embed(description="{dj_remove_user}", color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed, _id=member.id)

        await ctx.send(embed=embed)

    @commands.command(name='search')
    @require_voice_connection(should_connect=True)
    async def _search(self, ctx, *, query):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await player.node.get_tracks(query)

        embed = discord.Embed(description='{nothing_found}', color=0x36393F)
        if not results or not results['tracks']:
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)

        buttons = []
        for i, track in enumerate(results['tracks'], start=1):
            duration = timeformatter.format_ms(int(track.duration))
            interaction = SelectorItem(f'`{i}` [{track.title}]({track.uri}) `{duration}`', str(i),
                                       wrap_in_button_callback(
                                           self.enqueue, ctx, track, discord.Embed(color=ctx.me.color)))
            buttons.append(interaction)

        search_selector = Selector(ctx, buttons, select_mode=SelectMode.SingleSelect,
                                   color=ctx.me.color, title=ctx.localizer.format_str('{results}'))
        message, callback_results = await search_selector.start_scrolling()

        if len(callback_results) == 0:
            if message:
                await message.delete()
            return

        song_embed, song_added = callback_results[0]
        if song_added:
            embed = ctx.localizer.format_embed(song_embed)
            await message.edit(embed=embed, view=None)

            if not player.is_playing:
                await player.play()

    @commands.command(name='disconnect')
    @require_voice_connection()
    @voteable(DJ_override=True, react_to_vote=True)
    async def _disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

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
        """ Tries to disconnect then reconnect the player in case the bot gets stuck on a song """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        current_channel = player.channel_id

        async def recon():
            await player.stop()
            if ctx.voice_client:
                await ctx.voice_client.disconnect()
                await asyncio.sleep(1)  # Pretend stuff is happening/give everything some time to reset.
                channel = ctx.guild.get_channel(current_channel)
                await channel.connect(cls=BasicVoiceClient)

        if player.current:
            track = player.current
            start_time = player.position
            await recon()
            if track:
                await player.play(track, start_time=start_time)
        else:
            await recon()

    @commands.command(name='volume')
    @checks.dj_or(alone=True, track_requester=True)
    @require_playing(require_user_listening=True)
    async def _volume(self, ctx, volume: int = None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

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

    @commands.command(name='forceplay')
    @require_voice_connection(should_connect=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _forceplay(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

        if not results or not results.tracks:
            return await ctx.send(ctx.localizer.format_str("{nothing_found}"))

        embed = discord.Embed(color=ctx.me.color)

        if results.load_type == 'PLAYLIST_LOADED':
            numtracks = 0
            for track in results.tracks:
                _, track_added = await self.enqueue(ctx, track, embed, silent=True, check_max_length=False)
                if track_added:
                    numtracks += 1

            embed.title = '{playlist_enqued}'
            embed.description = f'{results.playlist_info.name} - {numtracks} {{tracks}}'
        else:
            track = results.tracks[0]
            await self.enqueue(ctx, track, embed, check_max_length=False)

        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()

    @commands.command(name='forcedisconnect')
    @checks.dj_or(alone=True)
    async def _forcedisconnect(self, ctx):
        """ Attempts to force disconnect the bot without checking if it is connected initially. """
        try:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
            player.queue.clear()
            await player.stop()
        except Exception:
            self.logger.exception("Error forcedisconnecting")
        await ctx.voice_client.disconnect(force=True)
        embed = discord.Embed(description='{disconnect.disconnected}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='normalize')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    async def _normalize(self, ctx):
        """ Reset the equalizer and volume """
        player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.set_volume(100)
        await player.bassboost(False)

        embed = discord.Embed(description='{volume.reset}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='boost')
    @checks.dj_or(alone=True)
    async def _boost(self, ctx, boost: bool = False):
        """ Set the equalizer to bass boost the music """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if boost is not None:
            await player.bassboost(boost)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = '{boost.on}' if player.boosted else '{boost.off}'

        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='nightcore')
    @checks.dj_or(alone=True)
    async def _nightcore(self, ctx, boost: bool = False):
        """ Set a filter mimicking nightcore the music """
        player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.nightcoreify(boost)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = '{nightcore.on}' if player.nightcore_enabled else '{nightcore.off}'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='history')
    async def _history(self, ctx):
        """ Show the last 10 songs played """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
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

        if thumbnail_url := player.current.extra["thumbnail_url"]:
            embed.set_thumbnail(url=thumbnail_url)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.command(name='lyrics')
    async def _lyrics(self, ctx, *query: str):

        # TODO:
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        genius_access_token = self.bot.APIkeys.get('genius', None)

        if genius_access_token is None:
            return await ctx.send('Missing API key')

        excluded_words = ['music', 'video', 'version', 'original', 'lyrics', 'lyric',
                          'official', 'live', 'instrumental', 'audio', 'hd']

        query = ' '.join(query)

        if not query and player.is_playing:
            query = player.current.title
            query = re.sub(r'[-()_\[\]]', '', query)
            filtered_words = [word for word in query.split() if word.lower() not in excluded_words]
            query = ' '.join(filtered_words)

        async def get_site_content(url):
            async with self.bot.session.get(url) as resp:
                response = await resp.read()
            return response.decode('utf-8')

        embed = discord.Embed(description=':mag_right:')
        status_msg = await ctx.send(embed=embed)

        try:
            url = 'https://api.genius.com/search?' + urllib.parse.urlencode(
                    {'access_token': genius_access_token, 'q': query})
            result = await get_site_content(url)
            response = json.loads(result)
            song_id = response['response']['hits'][0]['result']['id']
        except Exception:
            embed = discord.Embed(description=':x:', color=0xFF0000)
            return await status_msg.edit(embed=embed)

        result = await get_site_content(f'https://api.genius.com/songs/{song_id}?access_token={genius_access_token}')
        song = json.loads(result)['response']['song']

        response = await get_site_content(song['url'])
        scraped_data = BeautifulSoup(response, 'html.parser')
        lyrics = scraped_data.find(class_='lyrics').get_text()

        paginator = TextPaginator(max_size=2000, max_lines=50, color=0xFFFF64)
        for line in lyrics.split('\n'):
            paginator.add_line(line)

        await status_msg.delete()

        paginator.pages[0].url = song['url']
        paginator.pages[0].title = song['full_title']
        paginator.pages[0].set_thumbnail(url=song['header_image_thumbnail_url'])
        paginator.pages[0].set_author(name='Genius', icon_url='https://i.imgur.com/NmCTsoF.png')

        if len(paginator.pages) < 4:
            for page in paginator.pages:
                await ctx.send(embed=page)
        else:
            paginator.add_page_indicator(ctx.localizer)
            await Scroller(ctx, paginator).start_scrolling(ClearOn.AnyExi)

    @commands.command(name='scrub')
    @checks.dj_or(alone=True)
    @require_voice_connection()
    @require_playing(require_user_listening=True)
    async def _scrub(self, ctx):
        """ Shows a set of controls which can be used to skip forward or backwards in the song """
        player: MixPlayer = self.bot.lavalink.player_manager.get(ctx.guild.id)
        controls = '{scrub.controls}'

        def seek_callback(player: MixPlayer, seconds):
            async def inner(_interaction, _button):
                newpos = player.position + seconds * 1000
                return await player.seek(newpos)
            return inner

        def toggle_pause_callback(player: MixPlayer):
            async def inner(_interaction, button):
                should_pause = not player.paused
                button.style = discord.ButtonStyle.red if should_pause else discord.ButtonStyle.gray
                return await player.set_pause(should_pause)
            return inner

        scrubber_controls = [
            SelectorItem("", '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', seek_callback(player, -1000)),
            SelectorItem("", '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}', seek_callback(player, -15)),
            SelectorItem("", '\N{Black Right-Pointing Triangle with Double Vertical Bar}',
                         toggle_pause_callback(player)),
            SelectorItem("", '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}', seek_callback(player, 15)),
            SelectorItem("", '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', seek_callback(player, 1000))
        ]
        scrubber = Selector(ctx, scrubber_controls, select_mode=SelectMode.MultiSelect, use_tick_for_stop_emoji=True,
                            default_text=ctx.localizer.format_str(controls), color=ctx.me.color)
        await scrubber.start_scrolling(ClearOn.AnyExit)

    @commands.group(name='loop')
    async def _loop(self, ctx):
        # This is done using subcommands to have separate vote counts for starting and stopping.
        if ctx.invoked_subcommand is None:
            player = self.bot.lavalink.player_manager.get(ctx.guild.id)
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
        """ Set the equalizer to bass boost the music """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.enable_looping(True)
        embed = discord.Embed(color=ctx.me.color)
        embed.description = 'Looping turned on'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @_loop.command(name='stop')
    @require_playing(require_user_listening=True)
    @voteable(DJ_override=True, react_to_vote=True)
    async def _loop_stop(self, ctx):
        """ Set the equalizer to bass boost the music """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.enable_looping(False)
        embed = discord.Embed(color=ctx.me.color)
        embed.description = 'Looping turned off'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    async def cog_unload(self):
        self.bot.lavalink._event_hooks.clear()

    async def track_hook(self, event):
        if isinstance(event, TrackEndEvent):
            channel = self.bot.get_channel(event.player.fetch('channel'))
            player = self.bot.lavalink.player_manager.get(channel.guild.id)
            player.skip_voters.clear()

        if isinstance(event, TrackStartEvent):
            pass
        if isinstance(event, QueueEndEvent):
            channel = self.bot.get_channel(event.player.fetch('channel'))
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
    async def on_voice_state_update(self, member, before, after):
        """ Updates listeners when the bot or a user changes voice state """
        if member.id == self.bot.user.id and after.channel is not None:
            voice_channel = after.channel
            player = self.bot.lavalink.player_manager.get(member.guild.id)
            player.clear_listeners()
            for member in voice_channel.members:
                if not member.bot:
                    player.update_listeners(member, member.voice)

        if not member.bot:
            player = self.bot.lavalink.player_manager.get(member.guild.id)
            if player is not None:
                player.update_listeners(member, after)
                await self.check_leave_voice(member.guild)

    async def check_leave_voice(self, guild):
        """ Checks if the bot should leave the voice channel """
        # TODO, disconnect timer?
        player = self.bot.lavalink.player_manager.get(guild.id)
        if len(player.listeners) == 0 and player.is_connected:
            if player.queue.empty and player.current is None:
                await player.stop()
                await guild.voice_client.disconnect()

    async def leave_check(self):
        for player_id in self.bot.lavalink.player_manager.players:
            await self.check_leave_voice(self.bot.get_guild(player_id))

    @tasks.loop(seconds=10.0)
    async def leave_timer(self):
        try:
            await self.leave_check()
        except Exception as err:
            self.logger.debug("Error in leave_timer loop.\nTraceback: %s" % (err))


def wrap_in_button_callback(func, *args):
    async def inner(_interaction, _button):
        return await func(*args)
    return inner


async def setup(bot):
    await bot.add_cog(Music(bot))
