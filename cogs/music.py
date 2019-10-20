"""
Music commands
"""
import math
import re
import asyncio
import yaml
import codecs

import lavalink
import discord
from discord.ext import commands
from typing import Optional

import urllib
import json
from bs4 import BeautifulSoup

from .utils import checks, RoxUtils, timeformatter
from .utils.mixplayer import MixPlayer
from .utils.paginator import QueuePaginator, TextPaginator, Scroller

from .utils.selector import Selector

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("Music")
        if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            bot.lavalink = lavalink.Client(bot.user.id, player=MixPlayer)

            with codecs.open(f"{self.bot.datadir}/config.yaml", 'r', encoding='utf8') as f:
                conf = yaml.load(f, Loader=yaml.SafeLoader)

            bot.lavalink.add_node(**conf['lavalink nodes']['main'])
            self.logger.debug("Adding Lavalink node")
            bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')

    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        textchannels = self.bot.settings.get(ctx.guild, 'channels.text', [])
        if textchannels:
            if ctx.channel.id not in textchannels:
                return False
        return True

    async def cog_before_invoke(self, ctx):
        await self.ensure_voice(ctx)

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)

    @commands.command(name='play')
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
            tracks = results['tracks']

            maxlength = self.max_track_length(ctx.guild, player)
            if maxlength:
                numtracks = 0
                for track in tracks:
                    if track['info']['length'] <= maxlength:
                        player.add(requester=ctx.author.id, track=track)
                        numtracks += 1
            else:
                numtracks = len(tracks)
                for track in tracks:
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
    @checks.dj_or(alone=True)
    async def _seek(self, ctx, *, time: str):
        """ Seeks to a given position in a track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(ctx.localizer.format_str("{not_playing}"))

        if ctx.author not in player.listeners:
            return await ctx.send(ctx.localizer.format_str("{have_to_listen}"))

        seconds = time_rx.search(time)
        if not seconds:
            return await ctx.send(ctx.localizer.format_str("{seek.missing_amount}"))

        seconds = int(seconds.group()) * 1000
        if time.startswith('-'):
            seconds *= -1

        track_time = player.position + seconds
        await player.seek(track_time)
        msg = ctx.localizer.format_str("{seek.track_moved}", _position=timeformatter.format_ms(track_time))
        await ctx.send(msg)

    @commands.command(name='skip')
    async def _skip(self, ctx):
        """ Skips the current track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(ctx.localizer.format_str("{not_playing}"))

        player.add_skipper(ctx.author)
        total = len(player.listeners)
        skips = len(player.skip_voters)
        threshold = self.bot.settings.get(ctx.guild, 'vote_threshold', 'default_threshold')

        if skips/total >= threshold/100 or player.current.requester == ctx.author.id:
            await player.skip()
            if player.current:
                song = f'**[{player.current.title}]({player.current.uri})**'
                embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')
                thumbnail_url = await RoxUtils.ThumbNailer.identify(self, player.current.identifier, player.current.uri)
                member = ctx.guild.get_member(player.current.requester)
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                if member.nick:
                    member_identifier = member.nick
                else:
                    member_identifier = member.name
                embed.set_footer(text=f'{{requested_by}} {member_identifier}', icon_url=member.avatar_url)

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
    async def _skip_to(self, ctx, pos: int = 1):
        """ Plays the queue from a specific point. Disregards tracks before the pos. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if ctx.author not in player.listeners:
            return await ctx.send(ctx.localizer.format_str("{have_to_listen}"))

        if pos < 1:
            return await ctx.send(ctx.localizer.format_str("{skip_to.invalid_pos}"))
        if len(player.queue) < pos:
            return await ctx.send(ctx.localizer.format_str("{skip_to.exceeds_queue}"))
        await player.skip(pos - 1)
        msg = ctx.localizer.format_str("{skip_to.skipped_to}", _title=player.current.title, _pos=pos)
        await ctx.send(msg)

    @commands.command(name='stop')
    @checks.dj_or(alone=True)
    async def _stop(self, ctx):
        """ Stops the player and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if ctx.author not in player.listeners:
            return await ctx.send(ctx.localizer.format_str("{have_to_listen}"))

        if not player.is_playing:
            return await ctx.send(ctx.localizer.format_str("{not_playing}"))

        player.queue.clear()
        await player.stop()
        await ctx.send(ctx.localizer.format_str("{stop}"))

    @commands.command(name='now')
    async def _now(self, ctx):
        """ Shows some stats about the currently playing song. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.current:
            return await ctx.send(ctx.localizer.format_str("{not_playing}"))

        position = timeformatter.format_ms(player.position)
        if player.current.stream:
            duration = '{live}'
        else:
            duration = timeformatter.format_ms(player.current.duration)
        song = f'**[{player.current.title}]({player.current.uri})**\n({position}/{duration})'

        member = ctx.guild.get_member(player.current.requester)
        embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')
        thumbnail_url = await RoxUtils.ThumbNailer.identify(self, player.current.identifier, player.current.uri)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if member.nick:
            member_identifier = member.nick
        else:
            member_identifier = member.name
        embed.set_footer(text=f'{{requested_by}} {member_identifier}', icon_url=member.avatar_url)

        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='queue')
    async def _queue(self, ctx, user: discord.Member = None):
        """ Shows the player's queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if player.queue.empty:
            embed = discord.Embed(description='{queue.empty}', color=ctx.me.color)
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)

        if user is None:
            queue = player.global_queue()
            pagified_queue = QueuePaginator(ctx.localizer, queue, color=ctx.me.color)

        else:
            user_queue = player.user_queue(user.id, dual=True)
            if not user_queue:
                return await ctx.send(ctx.localizer.format_str("{queue.empty}", _user=user.name))
            pagified_queue = QueuePaginator(ctx.localizer, user_queue, color=ctx.me.color, user_name=user.name)

        scroller = Scroller(ctx, pagified_queue)
        await scroller.start_scrolling()

    @commands.command(name='myqueue')
    async def _myqueue(self, ctx):
        """ Shows your queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        user_queue = player.user_queue(ctx.author.id, dual=True)
        if not user_queue:
            return await ctx.send(ctx.localizer.format_str("{my_queue}"))

        pagified_queue = QueuePaginator(ctx.localizer, user_queue, color=ctx.me.color, user_name=ctx.author.name)
        scroller = Scroller(ctx, pagified_queue)
        await scroller.start_scrolling()

    @commands.command(name='pause')
    @checks.dj_or(alone=True)
    async def _pause(self, ctx):
        """ Pauses/Resumes the current track. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(ctx.localizer.format_str("{not_playing}"))

        if player.paused:
            await player.set_pause(False)
            await ctx.send(ctx.localizer.format_str("{resume.resumed}"))
        else:
            await player.set_pause(True)
            await ctx.send(ctx.localizer.format_str("{resume.paused}"))

    @commands.command(name='shuffle')
    async def _shuffle(self, ctx):
        """ Shuffles your queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        user_queue = player.user_queue(ctx.author.id)

        if not user_queue:
            return await ctx.send(ctx.localizer.format_str("{my_queue}"))

        player.shuffle_user_queue(ctx.author.id)
        await ctx.send(ctx.localizer.format_str("{shuffle}"))

    @commands.command(name='move')
    async def _move(self, ctx):
        """ Moves a song in your queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if player.queue.empty:
            return

        user_queue = player.user_queue(ctx.author.id, dual=True)
        if not user_queue:
            return await ctx.send(ctx.localizer.format_str("{my_queue}"))
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
        thumbnail_url = await RoxUtils.ThumbNailer.identify(self, moved.identifier, moved.uri)
        member = ctx.guild.get_member(moved.requester)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if member.nick:
            member_identifier = member.nick
        else:
            member_identifier = member.name

        embed.add_field(name="{moved.local}", value=f"`{pos_initial + 1} → {pos_final + 1}`", inline=True)
        embed.add_field(name="{moved.global}", value=f"`{player.queue._loc_to_glob(ctx.author.id, pos_initial) + 1}\
         → {player.queue._loc_to_glob(ctx.author.id, pos_final) + 1}`", inline=True)
        embed.set_footer(text=f'{{requested_by}} {member_identifier}', icon_url=member.avatar_url)
        embed = ctx.localizer.format_embed(embed)

        await message.edit(embed=embed)
        await message.clear_reactions()

    @commands.command(name='remove')
    async def _remove(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if player.queue.empty:
            return

        user_queue = player.user_queue(ctx.author.id, dual=True)
        if not user_queue:
            return await ctx.send(ctx.localizer.format_str("{my_queue}"))

        identifiers = []
        for index, temp in enumerate(user_queue):
            track, globpos = temp
            identifiers.append(ctx.localizer.format_str("{queue.usertrack}", _index=index+1,
                                                        _globalindex=globpos+1, _title=track.title,
                                                        _uri=track.uri))

        functions = [player.remove_user_track]*len(user_queue)
        arguments = [(ctx.author.id, i) for i in range(len(user_queue))]

        selector = Selector(ctx, identifiers, functions, arguments, num_selections=5, color=0xFF0000,
                            title='Remove song plz')
        message, page, removed = await selector.start_scrolling()
        await message.edit(content=ctx.localizer.format_str("{remove}", _title=removed.title), embed=None)
        await message.clear_reactions()

    @commands.command(name="DJremove")
    @checks.dj_or()
    async def _djremove(self, ctx, pos: int, user: discord.Member = None):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if user is None:
            if player.queue.empty:
                return

            if pos > len(player.queue) or pos < 1:
                return await ctx.send(ctx.localizer.format_str("{out_of_range}", _len=len(player.queue)))

            removed = player.remove_global_track(pos - 1)
            requester = self.bot.get_user(removed.requester)
            await ctx.send(ctx.localizer.format_str("{dj_removed}", _title=removed.title, _user=requester.name))

        else:
            if player.queue.empty:
                return

            user_queue = player.user_queue(user.id)
            if not user_queue:
                return

            if pos > len(user_queue) or pos < 1:
                return await ctx.send(ctx.localizer.format_str("{out_of_range}", _len=len(user_queue)))

            removed = player.remove_user_track(user.id, pos - 1)
            await ctx.send(ctx.localizer.format_str("{dj_removed}", _title=removed.title, _user=removed.requester.name))

    @commands.command(name='removeuser')
    @checks.dj_or(alone=True)
    async def _user_queue_remove(self, ctx, user: discord.Member):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if player.queue.empty:
            return

        user_queue = player.user_queue(user.id)
        if not user_queue:
            return

        player.remove_user_queue(user.id)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = "{dj_remove_user}"
        embed = ctx.localizer.format_embed(embed, _id=user.id)

        await ctx.send(embed=embed)

    @commands.command(name='search')
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
        await message.clear_reactions()

        if not player.is_playing:
            await player.play()

    @commands.command(name='disconnect')
    @checks.dj_or(alone=True)
    async def _disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            return await ctx.send(ctx.localizer.format_str("{not_connected}"))

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            return await ctx.send(ctx.localizer.format_str("{disconnect.not_in_voice}"))

        player.queue.clear()
        await player.stop()
        await self.connect_to(ctx.guild.id, None)
        embed = discord.Embed(description='{disconnect.disconnected}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='volume')
    @checks.dj_or(alone=True, track_requester=True)
    async def _volume(self, ctx, volume: int = None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not volume:
            return await ctx.send(f'🔈 | {player.volume}%')

        is_dj = checks.is_dj(ctx)
        is_admin = getattr(ctx.author.guild_permissions, 'administrator', None) is True
        if int(player.current.requester) == ctx.author.id and not is_dj and not is_admin:
            if not 50 <= volume <= 125:
                return await ctx.send(ctx.localizer.format_str("{volume.out_of_range}"))

        await player.set_volume(volume)
        embed = discord.Embed(color=ctx.me.color)
        embed.description = "{volume.set_to}"
        embed = ctx.localizer.format_embed(embed, _volume=player.volume)
        await ctx.send(embed=embed)

    @commands.command(name='normalize')
    @checks.dj_or(alone=True)
    async def _normalize(self, ctx):
        """ Reset the equalizer and  """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        await player.set_volume(100)
        await player.bassboost(False)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = '{volume.reset}'
        embed = ctx.localizer.format_embed(embed)

        await ctx.send(embed=embed)

    @commands.command(name='boost')
    @checks.dj_or(alone=True)
    async def _boost(self, ctx, boost: bool = None):
        """ Set the equalizer to bass boost the music """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if boost is not None:
            await player.bassboost(boost)

        embed = discord.Embed(color=ctx.me.color)

        if player.boosted:
            embed.description = '{boost.on}'
        else:
            embed.description = '{boost.off}'

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
        thumb_url = await RoxUtils.ThumbNailer.identify(self, track.identifier, track.uri)
        for index, track in enumerate(history[1:], start=1):
            description += ctx.localizer.format_str("{history.track}", _index=-index, _title=track.title,
                                                    _uri=track.uri, _id=track.requester) + '\n'

        embed = discord.Embed(title=ctx.localizer.format_str('{history.title}'), color=ctx.me.color,
                              description=description)

        if thumb_url:
            embed.set_thumbnail(url=thumb_url)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 5, commands.BucketType.guild)
    @commands.command(name='lyrics')
    async def _lyrics(self, ctx, *query: str):

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
    async def _scrub(self, ctx):
        """ Lists the first 10 search results from a given query. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        controls = '{scrub.controls}'
        embed = discord.Embed(description='{nothing_playing}', color=ctx.me.color)
        embed = ctx.localizer.format_embed(embed)

        if player.current is None:
            return await ctx.send(embed=embed)

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

        embed.description = '{scrub.add}'
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

    async def ensure_voice(self, ctx, do_connect: Optional[bool] = None):
        """ This check ensures that the bot and command author are in the same voicechannel. """

        # If region doesn't return a known server location
        try:
            region = ctx.guild.region.value
        except AttributeError:
            region = ctx.guild.region

        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=region)
        # Create returns a player if one exists, otherwise creates.

        # Add commands that require joining voice to work.
        should_connect = ctx.command.callback.__name__ in ('_play', '_find', '_search', '_sk')

        # Add commands that don't require the you being in voice.
        without_connect = ctx.command.callback.__name__ in ('_queue', '_history', '_now', '_lyrics')

        if without_connect:
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError('Join a voicechannel first.')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('Not connected.')

            voice_channel = ctx.author.voice.channel

            permissions = voice_channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

            voice_channels = self.bot.settings.get(ctx.guild, 'channels.music', [])

            if voice_channels:
                if voice_channel.id not in voice_channels:
                    response = ctx.localizer.format_str('{settings_check.voicechannel}')
                    for channel_id in voice_channels:
                        channel = ctx.guild.get_channel(channel_id)
                        if channel is not None:
                            response += f'{channel.name}, '
                    await ctx.send(response[:-2])
                    raise commands.CommandInvokeError('You need to be in the right voice channel')

            player.store('channel', ctx.channel.id)
            await self.connect_to(ctx.guild.id, str(ctx.author.voice.channel.id))

        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You need to be in my voicechannel.')

    async def enqueue(self, ctx, track, embed):

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        maxlength = self.max_track_length(ctx.guild, player)
        if maxlength and track['info']['length'] > maxlength:
            embed.description = ctx.localizer.format_str("{enqueue.toolong}",
                                                         _length=timeformatter.format_ms(track['info']['length']),
                                                         _max=timeformatter.format_ms(maxlength))
            return

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
        thumb_url = await RoxUtils.ThumbNailer.identify(self, track.identifier, track.uri)

        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        duration = timeformatter.format_ms(int(track.duration))
        embed.description = f'[{track.title}]({track.uri})\n**{duration}**'

        return embed

    def max_track_length(self, guild, player):
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

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if isinstance(err, commands.CheckFailure):
            textchannels = self.bot.settings.get(ctx.guild, 'channels.text', [])
            if textchannels:
                if ctx.channel.id not in textchannels:
                    response = ctx.localizer.format_str('{settings_check.textchannel}')
                    for channel_id in textchannels:
                        response += f'<#{channel_id}>, '
                    await ctx.send(response[:-2])


def setup(bot):
    bot.add_cog(Music(bot))
