"""
Music commands
"""
import math
import re
import asyncio
import time
import yaml
import codecs

import lavalink
import discord
from discord.ext import commands
from typing import Optional

from .utils import checks, RoxUtils
from .utils.mixplayer import MixPlayer
from .utils.embedscroller import QueueScroller
from .utils.localizer import LocalizerWrapper

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


class Music:
    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            bot.lavalink = lavalink.Client(bot.user.id, player=MixPlayer)

            with codecs.open("data/config.yaml", 'r', encoding='utf8') as f:
                conf = yaml.safe_load(f)

            bot.lavalink.add_node(**conf['lavalink nodes']['main'])
            bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')

    def getLocalizer(self, guild):
        lang = self.bot.settings.get(guild, 'locale', 'default_locale')
        return LocalizerWrapper(self.bot.localizer, lang, "music.response")


    async def __before_invoke(self, ctx):
        # TODO: rewrite this thing. Probably remove ensure_voice.

        guild_check = ctx.guild is not None
        #  This is essentially the same as `@commands.guild_only()`
        #  except it saves us repeating ourselves (and also a few lines).

        if guild_check:
            await self.ensure_voice(ctx)
            #  Ensure that the bot and command author share a mutual voicechannel.
        else:
            raise commands.NoPrivateMessage

        return guild_check

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)

    @commands.command(name='play', aliases=['p','spill','s','spel'])
    async def _play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)
        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send(localizer.format_str("{nothing_found}"))

        embed = discord.Embed(color=ctx.me.color)

        if results['loadType'] == 'PLAYLIST_LOADED':
            tracks = results['tracks']

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)

            embed.title = '{playlist_enqued}'
            embed.description = f'{results["playlistInfo"]["name"]} - {len(tracks)} {{tracks}}'
            embed = localizer.format_embed(embed)
            await ctx.send(embed=embed)
        else:
            track = results['tracks'][0]
            await self.enqueue(ctx, track, embed)
            embed = localizer.format_embed(embed)
            await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()

    @commands.command(name='seek', aliases=['spol'])
    @checks.DJ_or(alone=True)
    async def _seek(self, ctx, *, time: str):
        """ Seeks to a given position in a track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)
        
        if not player.is_playing:
            return await ctx.send(localizer.format_str("{not_playing}"))

        if ctx.author not in player.listeners:
            return await ctx.send(localizer.format_str("{have_to_listen}"))

        seconds = time_rx.search(time)
        if not seconds:
            return await ctx.send(localizer.format_str("{seek.missing_amount}"))

        seconds = int(seconds.group()) * 1000
        if time.startswith('-'):
            seconds *= -1

        track_time = player.position + seconds
        await player.seek(track_time)
        msg = localizer.format_str("{seek.track_moved}",_position=lavalink.utils.format_time(track_time))
        await ctx.send(msg)

    @commands.command(name='skip', aliases=['hopp'])
    async def _skip(self, ctx):
        """ Skips the current track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if not player.is_playing:
            return await ctx.send(localizer.format_str("{not_playing}"))

        player.add_skipper(ctx.author)
        total = len(player.listeners)
        skips = len(player.skip_voters)
        if skips >= math.ceil(total/2) or player.current.requester == ctx.author.id:
            await player.skip()
            await ctx.send(localizer.format_str("{skip.skipped}"))
        else:
            if skips != 0:
                msg = localizer.format_str("{skip.require_vote}", _skips=skips, _total=math.ceil(total/2))
                await ctx.send(msg)

    @commands.command(name='skipto', aliases=['forceskip','hopptil','tvinghopp'])
    @checks.DJ_or(alone=True)
    async def _skip_to(self, ctx, pos: int=1):
        """ Plays the queue from a specific point. Disregards tracks before the pos. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if ctx.author not in player.listeners:
            return await ctx.send(localizer.format_str("{have_to_listen}"))

        if pos < 1:
            return await ctx.send(localizer.format_str("{skip_to.invalid_pos}"))
        if len(player.queue) < pos:
            return await ctx.send(localizer.format_str("{skip_to.exceeds_queue}"))
        await player.skip(pos - 1)
        msg = localizer.format_str("{skip_to.skipped_to}", _title=player.current.title, _pos=pos)
        print(msg, player.current.title, pos)
        await ctx.send(msg)

    @commands.command(name='stop', aliases=['stopp'])
    @checks.DJ_or(alone=True)
    async def _stop(self, ctx):
        """ Stops the player and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if ctx.author not in player.listeners:
            return await ctx.send(localizer.format_str("{have_to_listen}"))

        if not player.is_playing:
            return await ctx.send(localizer.format_str("{not_playing}"))

        player.queue.clear()
        await player.stop()
        await ctx.send(localizer.format_str("{stop}"))

    @commands.command(name='now', aliases=['np','current', 'nå', 'nåspilles', 'gjeldende', 'spillernå','spelarno','nospelar'])
    async def _now(self, ctx):
        """ Shows some stats about the currently playing song. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if not player.current:
            return await ctx.send(localizer.format_str("{not_playing}"))

        position = lavalink.utils.format_time(player.position)
        if player.current.stream:
            duration = '{live}'
        else:
            duration = lavalink.utils.format_time(player.current.duration)
        song = f'**[{player.current.title}]({player.current.uri})**\n({position}/{duration})'

        member = ctx.guild.get_member(player.current.requester)
        embed = discord.Embed(color=ctx.me.color, description=song, title='{now}')
        thumbnail_url = await RoxUtils.ThumbNailer.identify(self,player.current.identifier, player.current.uri)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if member.nick:
            member_identifier = member.nick
        else:
            member_identifier = member.name
        embed.set_footer(text=f'{{requested_by}} {member_identifier}', icon_url=member.avatar_url)

        embed = localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='queue', aliases=['q', 'kø'])
    async def _queue(self, ctx, user: discord.Member=None):
        """ Shows the player's queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if player.queue.empty:
            return await ctx.send(localizer.format_str("{queue.empty}"))
        
        if user is None:
            queue = player.global_queue()
            scroller = QueueScroller(ctx, queue, localizer, lines_per_page=10)
            await scroller.start_scrolling()

        else:
            user_queue = player.user_queue(user.id, dual=True)
            if not user_queue:
                return await ctx.send(localizer.format_str("{queue.empty}", _user=user.name))
            
            scroller = QueueScroller(ctx, user_queue, localizer, lines_per_page=10, user_name=user.name)
            await scroller.start_scrolling()

    @commands.command(name='myqueue', aliases=['mq','minkø','mk'])
    async def _myqueue(self, ctx):
        """ Shows your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        user_queue = player.user_queue(ctx.author.id, dual=True)
        if not user_queue:
            return await ctx.send(localizer.format_str("{my_queue}"))

        scroller = QueueScroller(ctx, user_queue, localizer, lines_per_page=10, user_name=ctx.author.name)
        await scroller.start_scrolling()

    @commands.command(name='pause', aliases=['resume','gjenoppta'])
    @checks.DJ_or(alone=True)
    async def _pause(self, ctx):
        """ Pauses/Resumes the current track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if not player.is_playing:
            return await ctx.send(localizer.format_str("{not_playing}"))

        if player.paused:
            await player.set_pause(False)
            await ctx.send(localizer.format_str("{resume.resumed}"))
        else:
            await player.set_pause(True)
            await ctx.send(localizer.format_str("{resume.paused}"))

    @commands.command(name='shuffle', aliases=['stokk'])
    async def _shuffle(self, ctx):
        """ Shuffles your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        user_queue = player.user_queue(ctx.author.id)

        if not user_queue:
            return await ctx.send(localizer.format_str("{my_queue}"))

        player.shuffle_user_queue(ctx.author.id)
        await ctx.send(localizer.format_str("{shuffle}"))

    @commands.command(name='move', aliases=['m', 'flytt','f'])
    async def _move(self, ctx, from_pos: int, to_pos: int):
        """ Moves a song in your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        user_queue = player.user_queue(ctx.author.id)
        if not user_queue:
            return await ctx.send(localizer.format_str("{my_queue}"))

        if not all(x in range(1,len(user_queue) + 1) for x in [from_pos, to_pos]):
            return await ctx.send(localizer.format_str("{out_of_range}", _len=len(user_queue)))

        moved = player.move_user_track(ctx.author.id, from_pos - 1, to_pos - 1)
        if moved is None:
            return await ctx.send(localizer.format_str("{move.not_in_queue}"))
        
        msg = localizer.format_str("{move.moved_to}", _title=moved.title, _from=from_pos, _to=to_pos)
        await ctx.send(msg)

    @commands.command(name='remove', aliases=['rem', 'fjern'])
    async def _remove(self, ctx, pos: int):
        """ Removes an item from the player's queue with the given pos. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if player.queue.empty:
            return

        user_queue = player.user_queue(ctx.author.id)
        if not user_queue:
            return

        if pos > len(user_queue) or pos < 1:
            return await ctx.send(localizer.format_str("{out_of_range}", _len=len(user_queue)))

        removed = player.remove_user_track(ctx.author.id, pos - 1)

        await ctx.send(localizer.format_str("{remove}", _title=removed.title))

    @commands.command(name="DJremove", aliases=['DJfjern','djfjern'])
    @checks.DJ_or()
    async def _djremove(self, ctx, pos: int, user: discord.Member=None):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if user is None:
            if player.queue.empty:
                return

            if pos > len(player.queue) or pos < 1:
                return await ctx.send(localizer.format_str("{out_of_range}", _len=len(player.queue)))

            removed = player.remove_global_track(pos - 1)
            requester = self.bot.get_user(removed.requester)
            await ctx.send(localizer.format_str("{dj_removed}", _title=removed.title, _user=requester.name))

        else:
            if player.queue.empty:
                return

            user_queue = player.user_queue(user.id)
            if not user_queue:
                return

            if pos > len(user_queue) or pos < 1:
                return await ctx.send(localizer.format_str("{out_of_range}", _len=len(user_queue)))

            removed = player.remove_user_track(user.id, pos - 1)
            await ctx.send(localizer.format_str("{dj_removed}", _title=removed.title, _user=requester.name))

    @commands.command(name='removeuser', aliases=['fjernbruker','fjernbrukar'])
    @checks.DJ_or(alone=True)
    async def _user_queue_remove(self, ctx, user: discord.Member):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if player.queue.empty:
            return

        user_queue = player.user_queue(user.id)
        if not user_queue:
            return

        player.remove_user_queue(user.id)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = "{dj_remove_user}"
        embed = localizer.format_embed(embed, _id=user.id)

        await ctx.send(embed=embed)

    @commands.command(name='search', aliases=['søk','finn'])
    async def _search(self, ctx, *, query):
        """ Lists the first 10 search results from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await player.node.get_tracks(query)

        embed = discord.Embed(description='{nothing_found}', color=0x36393F)
        if not results or not results['tracks']:
            embed = localizer.format_embed(embed)
            return await ctx.send(embed=embed)

        tracks = results['tracks']
        result_count = min(len(tracks), 5)

        search_results = ''
        for index, track in enumerate(tracks, start=1):
            track_title = track['info']['title']
            track_uri = track['info']['uri']
            search_results += f'`{index}.` [{track_title}]({track_uri})\n'
            if index == result_count:
                break

        choices = [
            ('1\N{combining enclosing keycap}', 1),
            ('2\N{combining enclosing keycap}', 2),
            ('3\N{combining enclosing keycap}', 3),
            ('4\N{combining enclosing keycap}', 4),
            ('5\N{combining enclosing keycap}', 5),
        ]
        choice = None

        def check(reaction, user):
            if user is None or user.id != ctx.author.id:
                return False

            if reaction.message.id != result_msg.id:
                return False

            if reaction.emoji == '❌':
                return True

            for (emoji, index) in choices[:result_count]:
                if emoji == reaction.emoji:
                    nonlocal choice
                    choice = index
                    return True
            return False

        embed.description = '{search}'
        embed = localizer.format_embed(embed)
        result_msg = await ctx.send(embed=embed)

        for emoji, index in choices[:result_count]:
            await result_msg.add_reaction(emoji)
        await result_msg.add_reaction('❌')

        embed.description = search_results

        embed.title = '{results}'
        embed.color = ctx.me.color
        embed = localizer.format_embed(embed)

        await result_msg.edit(embed=embed)

        try:
            reaction, user = await self.bot.wait_for('reaction_add',
                                                     timeout=15.0,
                                                     check=check)
        except asyncio.TimeoutError:
            await result_msg.clear_reactions()
            embed.title = ''
            embed.description='{time_expired}'
            embed = localizer.format_embed(embed)
            await result_msg.edit(embed=embed)
            await asyncio.sleep(5)
            await result_msg.delete()
        else:
            if choice is None:
                await result_msg.delete()
            else:
                await result_msg.clear_reactions()
                track = tracks[choice - 1]
                await self.enqueue(ctx, track, embed)
                embed = localizer.format_embed(embed)
                await result_msg.edit(embed=embed)
                if not player.is_playing:
                    await player.play()

    @commands.command(name='disconnect', aliases=['dc','kf','koblefra','koblefrå'])
    @checks.DJ_or(alone=True)
    async def _disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if not player.is_connected:
            return await ctx.send(localizer.format_str("{not_connected}"))

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            return await ctx.send(localizer.format_str("{disconnect.not_in_voice}"))

        player.queue.clear()
        await player.stop()
        await self.connect_to(ctx.guild.id, None)
        embed = discord.Embed(description='{disconnect.disconnected}', color=ctx.me.color)
        embed = localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='volume', aliases=['vol', 'volum', 'lydstyrke'])
    @checks.DJ_or(alone=True, current=True)
    async def _volume(self, ctx, volume: int = None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if not volume:
            return await ctx.send(f'🔈 | {player.volume}%')

        # Hacky bs, redo when doing proper DJ role support.
        user_roles = [role.name for role in ctx.author.roles]
        DJ_roles = ['DJ','dj','Dj']
        is_dj = [i for i in DJ_roles if i in user_roles]
        is_admin = getattr(ctx.author.guild_permissions, 'administrator', None) == True
        if int(player.current.requester) == ctx.author.id and not is_dj and not is_admin:
            if not 50 <= volume <= 125:
                return await ctx.send(localizer.format_str("{volume.out_of_range}"))

        await player.set_volume(volume)
        embed = discord.Embed(color=ctx.me.color)
        embed.description = "{volume.set_to}"
        embed = localizer.format_embed(embed, _volume=player.volume)
        await ctx.send(embed=embed)

    @commands.command(name='nomalize', aliases=['normal','nl','normaliser'])
    @checks.DJ_or(alone=True)
    async def _normalize(self, ctx):
        """ Reset the equalizer and  """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        await player.set_volume(100)
        await player.bassboost(False)

        embed = discord.Embed(color=ctx.me.color)
        embed.description = '{volume.reset}'
        embed = localizer.format_embed(embed)

        await ctx.send(embed=embed)

    @commands.command(name='boost', aliases=['boo','bassforsterker','bassforsterkar'])
    @checks.DJ_or(alone=True)
    async def _boost(self, ctx, boost: bool=None):
        """ Set the equalizer to bass boost the music """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        if boost is not None:
            await player.bassboost(boost)

        embed = discord.Embed(color=ctx.me.color)

        if player.boosted:
            embed.description = '{boost.on}'
        else:
            embed.description = '{boost.off}'
        
        embed = localizer.format_embed(embed)
        await ctx.send(embed=embed)

    @commands.command(name='history', aliases=['h','hist','historie'])
    async def _history(self, ctx):
        """ Show the last 10 songs played """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)
        history = player.get_history()
        track = history[0]
        description = localizer.format_str("{history.current}", _title=track.title, _uri=track.uri,_id=track.requester) + '\n\n'
        description += localizer.format_str("{history.previous}", _len=len(history)-1) + '\n'
        thumb_url = await RoxUtils.ThumbNailer.identify(self,
                                                track.identifier,
                                                track.uri)
        for index, track in enumerate(history[1:], start=1):
            description += localizer.format_str("{history.track}",_index=-index, _title=track.title, _uri=track.uri, _id=track.requester) + '\n'

        embed = discord.Embed(title=localizer.format_str('{history.title}'), color=ctx.me.color, description=description)

        if thumb_url:
            embed.set_thumbnail(url=thumb_url)
        await ctx.send(embed=embed)


    @commands.command(name='scrub', aliases=['kontrol','konsoll'])
    @checks.DJ_or(alone=True)
    async def _scrub(self, ctx):
        """ Lists the first 10 search results from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        localizer = self.getLocalizer(ctx.guild)

        controls = '{scrub.controls}'
        embed = discord.Embed(description='{nothing_playing}', color=ctx.me.color)
        embed = localizer.format_embed(embed)

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
        embed = localizer.format_embed(embed)
        msg = await ctx.send(embed=embed)

        for (emoji, _, _) in scrubber:
            await msg.add_reaction(emoji)

        embed.description = controls
        embed = localizer.format_embed(embed)
        await msg.edit(embed=embed)
        scrubbing = True
        while scrubbing:
            try:
                reaction, user = await self.bot.wait_for('reaction_add',
                                                         timeout=15.0,
                                                         check=check)
            except asyncio.TimeoutError:
                scrolling = False
                try:
                    await msg.delete()
                    await ctx.message.delete()
                except:
                    pass
                finally:
                    break

            try:
                await msg.remove_reaction(reaction, user)
            except:
                pass
            if selection is not None:
                if not isinstance(arg, bool):
                    arg = player.position + arg * 1000
                await selection(arg)

    async def ensure_voice(self, ctx, do_connect: Optional[bool] = None):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.players.create(ctx.guild.id, endpoint=ctx.guild.region.value)
        # Create returns a player if one exists, otherwise creates.

        should_connect = ctx.command.name in ('play', "find", 'search')  # Add commands that require joining voice to work.

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError('Join a voicechannel first.')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('Not connected.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:  # Check user limit too?
                raise commands.CommandInvokeError('I need the `CONNECT` and `SPEAK` permissions.')

            player.store('channel', ctx.channel.id)
            await self.connect_to(ctx.guild.id, str(ctx.author.voice.channel.id))

        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You need to be in my voicechannel.')

    def max_track_length(self, guild):
        player = self.bot.lavalink.players.get(guild.id)
        if len(player.listeners):
            listeners = len(player.listeners)
        else:
            listeners = 1
        maxlen = max(60*60/listeners, 60*10)
        return maxlen

    async def enqueue(self, ctx, track, embed):

        player = self.bot.lavalink.players.get(ctx.guild.id)
        track, pos_global, pos_local = player.add(requester=ctx.author.id, track=track)
        localizer = self.getLocalizer(ctx.guild)

        if player.current is not None:
            queue_duration = 0
            for i, track in enumerate(player.queue):
                if i == pos_global:
                    break
                queue_duration += int(track.duration)

            until_play = queue_duration + player.current.duration - player.position
            until_play = lavalink.utils.format_time(until_play)
            embed.add_field(name="{enqueue.position}", value=f"`{pos_local + 1}({pos_global + 1})`", inline=True)
            embed.add_field(name="{enqueue.playing_in}", value=f"`{until_play} ({{enqueue.estimated}})`", inline=True)

        embed.title = '{enqueue.enqueued}'
        thumb_url = await RoxUtils.ThumbNailer.identify(self,
                                                        track.identifier,
                                                        track.uri)

        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        duration = lavalink.utils.format_time(int(track.duration))
        embed.description = f'[{track.title}]({track.uri})\n**{duration}**'

def setup(bot):
    bot.add_cog(Music(bot))
