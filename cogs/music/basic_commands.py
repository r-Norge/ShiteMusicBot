# Discord Packages
import discord
import lavalink
from discord.ext import commands

import asyncio
import json
import math
import re
import urllib

from bs4 import BeautifulSoup

from ..utils import checks, thumbnailer, timeformatter
from ..utils.decorators import require_playing, require_queue, require_voice_connection
from ..utils.paginator import QueuePaginator, Scroller, TextPaginator
from ..utils.selector import Selector

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


@commands.command(name='play')
@require_voice_connection(should_connect=True)
async def _play(self, ctx, *, query: str):
    """ Searches and plays a song from a given query. """
    # TODO: rework
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    query = query.strip('<>')

    if not url_rx.match(query):
        query = f'ytsearch:{query}'

    results = await player.node.get_tracks(query)

    if not results or not results['tracks']:
        return await ctx.send(ctx.localizer.format_str("{nothing_found}"))

    embed = discord.Embed(color=ctx.me.color)

    if results['loadType'] == 'PLAYLIST_LOADED':
        tracks = results['tracks']

        if maxlength := self.max_track_length(ctx.guild, player):
            numtracks = 0
            for track in tracks:
                if track['info']['length'] <= maxlength:
                    thumbnail_url = await thumbnailer.ThumbNailer.identify(
                        self, track['info']['identifier'], track['info']['uri'])
                    track = lavalink.models.AudioTrack(track, ctx.author.id, thumbnail_url=thumbnail_url)
                    player.add(requester=ctx.author.id, track=track)
                    numtracks += 1
        else:
            numtracks = len(tracks)
            for track in tracks:
                thumbnail_url = await thumbnailer.ThumbNailer.identify(
                    self, track['info']['identifier'], track['info']['uri'])
                track = lavalink.models.AudioTrack(track, ctx.author.id, thumbnail_url=thumbnail_url)
                player.add(requester=ctx.author.id, track=track)

        embed.title = '{playlist_enqued}'
        embed.description = f'{results["playlistInfo"]["name"]} - {numtracks} {{tracks}}'
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)
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
async def _skip(self, ctx):
    # TODO: rework
    """ Skips the current track. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    player.add_skipper(ctx.author)
    total = len(player.listeners)
    skips = len(player.skip_voters)
    threshold = self.bot.settings.get(ctx.guild, 'vote_threshold', 'default_threshold')

    if skips/total >= threshold/100 or player.current.requester == ctx.author.id:
        await player.skip()
        if player.current:
            song = f'**[{player.current.title}]({player.current.uri})**'
            embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')
            thumbnail_url = player.current.extra["thumbnail_url"]
            member = ctx.guild.get_member(player.current.requester)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            embed.set_footer(text=f'{{requested_by}} {member.display_name}', icon_url=member.avatar_url)

            embed = ctx.localizer.format_embed(embed)
            await ctx.send(ctx.localizer.format_str("{skip.skipped}"), embed=embed)
        else:
            await ctx.send(ctx.localizer.format_str("{skip.skipped}"))
    else:
        if skips != 0:
            needed = math.ceil(total*threshold/100)
            msg = ctx.localizer.format_str("{skip.require_vote}", _skips=skips, _total=needed)

            await ctx.send(msg)


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
@checks.dj_or(alone=True)
@require_voice_connection()
@require_playing(require_user_listening=True)
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
    # TODO: rework
    """ Shows some stats about the currently playing song. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    position = timeformatter.format_ms(player.position)
    if player.current.stream:
        duration = '{live}'
    else:
        duration = timeformatter.format_ms(player.current.duration)
    song = f'**[{player.current.title}]({player.current.uri})**\n({position}/{duration})'

    member = ctx.guild.get_member(player.current.requester)
    embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')
    thumbnail_url = player.current.extra["thumbnail_url"]
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    embed.set_footer(text=f'{{requested_by}} {member.display_name}', icon_url=member.avatar_url)

    embed = ctx.localizer.format_embed(embed)
    await ctx.send(embed=embed)


@commands.command(name='queue')
@require_queue(require_member_queue=True)
async def _queue(self, ctx, *, member: discord.Member = None):
    """ Shows the player's queue. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    if member is None:
        queue = player.global_queue()
        pagified_queue = QueuePaginator(ctx.localizer, queue, color=ctx.me.color)

    else:
        member_queue = player.user_queue(member.id, dual=True)

        pagified_queue = QueuePaginator(ctx.localizer, member_queue, color=ctx.me.color,
                                        user_name=member.display_name)

    scroller = Scroller(ctx, pagified_queue)
    await scroller.start_scrolling()


@commands.command(name='myqueue')
@require_queue(require_author_queue=True)
async def _myqueue(self, ctx):
    """ Shows your queue. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    user_queue = player.user_queue(ctx.author.id, dual=True)
    pagified_queue = QueuePaginator(ctx.localizer, user_queue, color=ctx.me.color,
                                    user_name=ctx.author.display_name)
    scroller = Scroller(ctx, pagified_queue)
    await scroller.start_scrolling()


@commands.command(name='pause')
@checks.dj_or(alone=True)
@require_voice_connection()
@require_playing()
async def _pause(self, ctx):
    """ Pauses/Resumes the current track. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    if player.paused:
        await player.set_pause(False)
        await ctx.send(ctx.localizer.format_str("{resume.resumed}"))
    else:
        await player.set_pause(True)
        await ctx.send(ctx.localizer.format_str("{resume.paused}"))


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
    pos_initial, pos_final = selections[0], selections[1]

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
    await message.edit(content=ctx.localizer.format_str("{remove}", _title=removed.title), embed=None)


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
        await ctx.send(ctx.localizer.format_str("{dj_removed}", _title=removed.title, _user=requester.name))
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
        track_title = track['info']['title']
        track_uri = track['info']['uri']
        duration = timeformatter.format_ms(int(track['info']['length']))
        identifiers.append(f'`{index}.` [{track_title}]({track_uri}) `{duration}`')
        if index == result_count:
            break

    search_selector = Selector(ctx, identifiers, functions, arguments, num_selections=5,
                               color=ctx.me.color, title=ctx.localizer.format_str('{results}'))
    # Let the user scroll through results
    message, current_page, result = await search_selector.start_scrolling()

    result = ctx.localizer.format_embed(result)
    await message.edit(embed=result)

    if not player.is_playing:
        await player.play()


@commands.command(name='disconnect')
@checks.dj_or(alone=True)
@require_voice_connection()
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
@checks.dj_or(alone=True)
@require_voice_connection()
async def _reconnect(self, ctx):
    """ Tries to disconnect then reconnect the player in case the bot gets stuck on a song """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)
    current_channel = player.channel_id

    await player.stop()
    await self.connect_to(ctx.guild.id, None)
    await asyncio.sleep(1)  # Pretend stuff is happening/give everything some time to reset.
    await self.connect_to(ctx.guild.id, current_channel)
    await player.play()


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


@commands.command(name='normalize')
@checks.dj_or(alone=True)
@require_voice_connection()
async def _normalize(self, ctx):
    """ Reset the equalizer and volume """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    await player.set_volume(100)
    await player.bassboost(False)

    embed = discord.Embed(description='{volume.reset}', color=ctx.me.color)
    embed = ctx.localizer.format_embed(embed)
    await ctx.send(embed=embed)


@commands.command(name='boost')
@checks.dj_or(alone=True)
async def _boost(self, ctx, boost: bool = None):
    """ Set the equalizer to bass boost the music """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    if boost:
        await player.bassboost(boost)

    embed = discord.Embed(color=ctx.me.color)
    embed.description = '{boost.on}' if player.boosted else '{boost.off}'

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
    thumbnail_url = track.extra["thumbnail_url"]
    for index, track in enumerate(history[1:], start=1):
        description += ctx.localizer.format_str("{history.track}", _index=-index, _title=track.title,
                                                _uri=track.uri, _id=track.requester) + '\n'

    embed = discord.Embed(title=ctx.localizer.format_str('{history.title}'), color=ctx.me.color,
                          description=description)

    if thumbnail_url:
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
        await Scroller(ctx, paginator).start_scrolling()


@commands.command(name='scrub')
@checks.dj_or(alone=True)
@require_voice_connection()
@require_playing(require_user_listening=True)
async def _scrub(self, ctx):
    """ Lists the first 10 search results from a given query. """
    player = self.bot.lavalink.player_manager.get(ctx.guild.id)

    controls = '{scrub.controls}'

    scrubber = [
        ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', player.seek, -1000),
        ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}', player.seek, -15),
        ('\N{DOUBLE VERTICAL BAR}', player.set_pause, True),
        ('\N{BLACK RIGHT-POINTING TRIANGLE}', player.set_pause, False),
        ('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}', player.seek, 15),
        ('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', player.seek, 1000),
    ]

    selection = None
    arg = None

    def check(reaction, user):
        if user is None or user.id != ctx.author.id:
            return False

        if reaction.message.id != msg.id:
            return False

        for (emoji, func, _arg) in scrubber:
            if emoji == reaction.emoji:
                nonlocal selection
                nonlocal arg
                selection = func
                arg = _arg
                return True
        return False

    embed = discord.Embed(description='{scrub.add}', color=ctx.me.color)
    embed = ctx.localizer.format_embed(embed)
    msg = await ctx.send(embed=embed)

    for (emoji, _, _) in scrubber:
        await msg.add_reaction(emoji)

    embed.description = controls
    embed = ctx.localizer.format_embed(embed)
    await msg.edit(embed=embed)
    scrubbing = True
    while scrubbing:
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=15.0, check=check)
        except asyncio.TimeoutError:
            # PEP8EDIT scrolling = False
            try:
                await msg.delete()
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass
            finally:
                break

        try:
            await msg.remove_reaction(reaction, user)
        except discord.Forbidden:
            pass
        if selection is not None:
            if not isinstance(arg, bool):
                arg = player.position + arg * 1000
            await selection(arg)