"""
Commands that interact with just discord and lavalink and only present the basic commands needed for a music bot
"""

# Discord Packages
import discord
from discord.ext import commands

import asyncio
import re

from ..utils import checks, timeformatter
from ..utils.paginator import QueuePaginator, Scroller
from ..utils.selector import Selector
from .decorators import require_playing, require_queue, require_voice_connection, voteable

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


@commands.command(name='play')
@require_voice_connection(should_connect=True)
async def _play(self, ctx, *, query: str):
    """ Searches and plays a song from a given query. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    query = query.strip('<>')

    if not url_rx.match(query):
        query = f'ytsearch:{query}'

    results = await player.node.get_tracks(query)

    if not results or not results['tracks']:
        return await ctx.send(ctx.localizer.format_str("{nothing_found}"))

    embed = discord.Embed(color=ctx.me.color)

    if results['loadType'] == 'PLAYLIST_LOADED':
        numtracks = 0
        for track in results['tracks']:
            _, track_added = await self.enqueue(ctx, track, embed, silent=True)
            if track_added:
                numtracks += 1

        embed.title = '{playlist_enqued}'
        embed.description = f'{results["playlistInfo"]["name"]} - {numtracks} {{tracks}}'
    else:
        track = results['tracks'][0]
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
    if player.current:
        embed = self.get_current_song_embed(ctx)
        await ctx.send(ctx.localizer.format_str("{skip.skipped}"), embed=embed)
    else:
        await ctx.send(ctx.localizer.format_str("{skip.skipped}"))


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
    embed = self.get_current_song_embed(ctx, include_time=True)
    embed = ctx.localizer.format_embed(embed)
    await ctx.send(embed=embed)


@commands.command(name='queue')
@require_queue(require_member_queue=True)
async def _queue(self, ctx, *, member: discord.Member = None):
    """ Shows the player's queue. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    pagified_queue = QueuePaginator(ctx.localizer, player, color=ctx.me.color, member=member)
    scroller = Scroller(ctx, pagified_queue)
    await scroller.start_scrolling()


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
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    user_queue = player.user_queue(ctx.author.id, dual=True)

    # Setup for selector
    identifiers = []
    for index, temp in enumerate(user_queue):
        track, globpos = temp
        identifiers.append(ctx.localizer.format_str("{queue.usertrack}", _index=index+1,
                                                    _globalindex=globpos+1, _title=track.title,
                                                    _uri=track.uri))

    def ret_first_arg(*args):
        return args[0]

    functions = [ret_first_arg]*len(user_queue)
    arguments = [(i,) for i in range(len(user_queue))]

    # Set the different titles for the different selections
    round_titles = ["{moved.choose_song}", "{moved.choose_pos}"]
    round_titles = [ctx.localizer.format_str(i) for i in round_titles]

    selector = Selector(ctx, identifiers, functions, arguments, num_selections=5, round_titles=round_titles,
                        color=ctx.me.color, title=ctx.localizer.format_str("{moved.choose}"))

    # Get the initial and final position
    message, page, selections = await selector.start_scrolling()

    try:
        pos_initial, pos_final = selections[0], selections[1]
    except (IndexError, TypeError):
        return await message.delete()

    # Move the track
    moved = player.move_user_track(ctx.author.id, pos_initial, pos_final)

    # Create a nice embed explaining what happened
    song = f'**[{moved.title}]({moved.uri})**'
    embed = discord.Embed(color=ctx.me.color, description=song, title='{moved.moved}')
    thumbnail_url = moved.extra["thumbnail_url"]
    member = ctx.guild.get_member(moved.requester)
    if thumbnail_url:

        embed.set_thumbnail(url=thumbnail_url)

    embed.add_field(name="{moved.local}", value=f"`{pos_initial + 1} → {pos_final + 1}`", inline=True)
    embed.add_field(name="{moved.global}", value=f"`{player.queue._loc_to_glob(ctx.author.id, pos_initial) + 1}\
        → {player.queue._loc_to_glob(ctx.author.id, pos_final) + 1}`", inline=True)
    embed.set_footer(text=f'{{requested_by}} {member.display_name}', icon_url=member.avatar_url)
    embed = ctx.localizer.format_embed(embed)

    await message.edit(embed=embed)


@commands.command(name='remove')
@require_voice_connection()
@require_queue(require_author_queue=True)
async def _remove(self, ctx):
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    user_queue = player.user_queue(ctx.author.id, dual=True)
    functions = [player.remove_user_track]*len(user_queue)
    arguments = [(ctx.author.id, i) for i in range(len(user_queue))]
    identifiers = []

    for index, temp in enumerate(user_queue):
        track, globpos = temp
        identifiers.append(ctx.localizer.format_str("{queue.usertrack}", _index=index+1,
                                                    _globalindex=globpos+1, _title=track.title,
                                                    _uri=track.uri))

    selector = Selector(ctx, identifiers, functions, arguments, num_selections=5, color=0xFF0000,
                        title='Remove song plz')
    message, _, removed = await selector.start_scrolling()
    if removed:
        await message.edit(content=ctx.localizer.format_str("{remove}", _title=removed.title), embed=None)
    else:
        await message.delete()


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

    tracks = results['tracks']
    result_count = min(len(tracks), 15)

    # Setup for the selector
    identifiers = []
    functions = [self.enqueue]*result_count
    arguments = [(ctx, tracks[i], discord.Embed(color=ctx.me.color)) for i in range(result_count)]

    for index, track in enumerate(tracks, start=1):
        track = track['info']
        duration = timeformatter.format_ms(int(track['length']))
        identifiers.append(f'`{index}.` [{track["title"]}]({track["uri"]}) `{duration}`')
        if index == result_count:
            break

    search_selector = Selector(ctx, identifiers, functions, arguments, num_selections=5,
                               color=ctx.me.color, title=ctx.localizer.format_str('{results}'))
    # Let the user scroll through results
    message, current_page, result = await search_selector.start_scrolling()

    if result:
        (embed, added) = result
        embed = ctx.localizer.format_embed(embed)
        await message.edit(embed=embed)

        if not player.is_playing:
            await player.play()
    else:
        await message.delete()


@commands.command(name='disconnect')
@require_voice_connection()
@voteable(DJ_override=True, react_to_vote=True)
async def _disconnect(self, ctx):
    """ Disconnects the player from the voice channel and clears its queue. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    player.queue.clear()
    await player.stop()
    await self.connect_to(ctx.guild.id, None)
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
        await self.connect_to(ctx.guild.id, None)
        await asyncio.sleep(1)  # Pretend stuff is happening/give everything some time to reset.
        await self.connect_to(ctx.guild.id, current_channel)

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

    if not results or not results['tracks']:
        return await ctx.send(ctx.localizer.format_str("{nothing_found}"))

    embed = discord.Embed(color=ctx.me.color)

    if results['loadType'] == 'PLAYLIST_LOADED':
        numtracks = 0
        for track in results['tracks']:
            _, track_added = await self.enqueue(ctx, track, embed, silent=True, check_max_length=False)
            if track_added:
                numtracks += 1

        embed.title = '{playlist_enqued}'
        embed.description = f'{results["playlistInfo"]["name"]} - {numtracks} {{tracks}}'
    else:
        track = results['tracks'][0]
        await self.enqueue(ctx, track, embed, check_max_length=False)

    embed = ctx.localizer.format_embed(embed)
    await ctx.send(embed=embed)

    if not player.is_playing:
        await player.play()
