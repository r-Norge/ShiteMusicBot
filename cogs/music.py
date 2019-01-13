#!/usr/bin/env python3

"""
This is an example code that shows how you would setup a simple music bot for Lavalink v3.
This example is only compatible with the discord.py rewrite branch.
Because of the F-Strings, you also must have Python 3.6 or higher installed.
"""

import logging
import math
import re
import typing
import time

import asyncio
import discord
from discord.ext import commands
import lavalink

from .utils import checks, RoxUtils
from .utils.mixplayer.mixplayer import MixPlayer
from .utils.embedscroller import QueueScroller
from lavasettings import *

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\/\/(?:www\.)?.+')


class Music:
    def __init__(self, bot):

        self.bot = bot

        if not hasattr(bot, 'lavalink'):
            lavalink.Client(bot=bot, password='youshallnotpass',
                            loop=bot.loop, log_level=logging.INFO,
                            host=host, ws_port=ws_port,
                            rest_port=rest_port,
                            player=MixPlayer)
            self.bot.lavalink.register_hook(self._track_hook)

    def __unload(self):
        for guild_id, player in self.bot.lavalink.players:
            self.bot.loop.create_task(player.disconnect())
            player.cleanup()
        # Clear the players from Lavalink's internal cache
        self.bot.lavalink.players.clear()
        self.bot.lavalink.unregister_hook(self._track_hook)

    async def __local_check(self, ctx):
        is_guild = ctx.guild is not None
        return is_guild

    async def _track_hook(self, event):
        if isinstance(event, lavalink.Events.StatsUpdateEvent):
            return
        channel = self.bot.get_channel(event.player.fetch('channel'))
        if not channel:
            return

        if isinstance(event, lavalink.Events.TrackStartEvent):
            embed = discord.Embed(title='Now playing:', description=event.track.title, color=0xEFD26C)
            thumbnail_url = await RoxUtils.ThumbNailer.identify(self, event.player.current.identifier, event.player.current.uri)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            await channel.send(embed=embed)
        elif isinstance(event, lavalink.Events.QueueEndEvent):
            await channel.send('Queue ended.')

    @commands.command(name='play', aliases=['p'])
    async def _play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await self.bot.lavalink.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('Nothing found!')

        embed = discord.Embed(color=0xEFD26C)

        if results['loadType'] == 'PLAYLIST_LOADED':
            tracks = results['tracks']

            for track in tracks:
                player.add(requester=ctx.author.id, track=track)

            embed.title = 'Playlist Enqueued!'
            embed.description = f'{results["playlistInfo"]["name"]} - {len(tracks)} tracks'
            await ctx.send(embed=embed)
        else:
            track = results['tracks'][0]
            embed.title = 'Track Enqueued'
            thumbnail_url = await RoxUtils.ThumbNailer.identify(self, track['info']['identifier'], track['info']['uri'])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
            await ctx.send(embed=embed)
            player.add(requester=ctx.author.id, track=track)

        if not player.is_playing:
            await player.play()

    @commands.command(name='playnow', aliases=['pn'])
    async def _playnow(self, ctx, *, query: str):
        """ Plays immediately a song. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.queue and not player.is_playing:
            return await ctx.invoke(self._play, query=query)

        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await self.bot.lavalink.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('Nothing found!')

        tracks = results['tracks']
        track = tracks.pop(0)

        if results['loadType'] == 'PLAYLIST_LOADED':
            for _track in tracks:
                player.add(requester=ctx.author.id, track=_track)

        await player.play_now(requester=ctx.author.id, track=track)

    @commands.command(name='skipto', aliases=['st'])
    @checks.is_DJ()
    async def _skip_to(self, ctx, index: int):
        """ Plays the queue from a specific point. Disregards tracks before the index. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if ctx.author not in player.listeners:
            return await ctx.send('You have to be listening to the bot')

        if index < 1:
            return await ctx.send('Invalid specified index.')
        if len(player.queue) < index:
            return await ctx.send('This index exceeds the queue\'s length.')
        await player.skip_to(index - 1)

    @commands.command(name='seek')
    @checks.is_DJ()
    async def _seek(self, ctx, *, time: str):
        """ Seeks to a given position in a track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send('Not playing.')

        if ctx.author not in player.listeners:
            return await ctx.send('You have to be listening to the bot')

        seconds = time_rx.search(time)
        if not seconds:
            return await ctx.send('You need to specify the amount of seconds to skip!')

        seconds = int(seconds.group()) * 1000
        if time.startswith('-'):
            seconds *= -1

        track_time = player.position + seconds
        await player.seek(track_time)

        await ctx.send(f'Moved track to **{lavalink.Utils.format_time(track_time)}**')

    @commands.command(name='skip', aliases=['forceskip', 'fs'])
    async def _skip(self, ctx):
        """ Skips the current track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send('Not playing.')

        player.add_skipper(ctx.author)
        total = len(player.listeners)
        skips = len(player.skip_voters)
        if skips >= math.ceil(total/2) or player.current.requester == ctx.author.id:
            await player.skip()
            await ctx.send('Skipped.')
        else:
            if skips != 0:
                await ctx.send(f'{skips} out of {math.ceil(total/2)} required haters have voted to skip.')

    @commands.command(name='stop')
    @checks.is_DJ()
    async def _stop(self, ctx):
        """ Stops the player and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if ctx.author not in player.listeners:
            return await ctx.send('You have to be listening to the bot')

        if not player.is_playing:
            return await ctx.send('Not playing.')

        player.queue.clear()
        await player.stop()
        await ctx.send('⏹ | Stopped.')

    @commands.command(name='now', aliases=['np', 'n', 'playing'])
    async def _now(self, ctx):
        """ Shows some stats about the currently playing song. """

        #def scrubber(song, length):


        player = self.bot.lavalink.players.get(ctx.guild.id)
        song = 'Nothing'

        if player.current:
            position = lavalink.Utils.format_time(player.position)
            if player.current.stream:
                duration = '🔴 LIVE'
            else:
                duration = lavalink.Utils.format_time(player.current.duration)
            song = f'**[{player.current.title}]({player.current.uri})**\n({position}/{duration})'

        embed = discord.Embed(color=0xEFD26C, title='Now Playing', description=song)

        thumbnail_url = await RoxUtils.ThumbNailer.identify(self, player.current.identifier, player.current.uri)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        await ctx.send(embed=embed)

    @commands.command(name='queue', aliases=['q'])
    async def _queue(self, ctx, user: discord.Member=None):
        """ Shows the global queue or another users queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        if player.queue.is_empty():
            return await ctx.send('The queue is empty')
        
        if user is None:
            queue = player.global_queue()
            scroller = QueueScroller(ctx, queue, lines_per_page=10)
            await scroller.start_scrolling()

        else:
            user_queue = player.user_queue(user.id, dual=True)
            if not user_queue:
                return await ctx.send(f'{user.name}\'s queue is empty')
            
            scroller = QueueScroller(ctx, user_queue, lines_per_page=10, user_name=user.name)
            await scroller.start_scrolling()

    @commands.command(name='myqueue', aliases=['mq'])
    async def _myqueue(self, ctx):
        """ Shows your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        user_queue = player.user_queue(ctx.author.id, dual=True)
        if not user_queue:
            return await ctx.send('Your queue is empty')

        scroller = QueueScroller(ctx, user_queue, lines_per_page=10, user_name=ctx.author.name)
        await scroller.start_scrolling()

    @commands.command(name='pause', aliases=['resume'])
    async def _pause(self, ctx):
        """ Pauses/Resumes the current track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send('Not playing.')

        if player.paused:
            await player.set_pause(False)
            await ctx.send('⏯ | Resumed')
        else:
            await player.set_pause(True)
            await ctx.send('⏯ | Paused')

    @commands.command(name='volume', aliases=['vol'])
    @checks.is_DJ()
    async def _volume(self, ctx, volume: int = None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not volume:
            return await ctx.send(f'🔈 | {player.volume}%')

        await player.set_volume(volume)
        await ctx.send(f'🔈 | Set to {player.volume}%')

    @commands.command(name='boost', aliases=['boo'])
    async def _boost(self, ctx, boost: bool=None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        if boost is None:
            if player.boosted:
                await ctx.send('Bass boost is on')
            else:
                await ctx.send('Bass boost is off')
        else:
            await player.bassboost(boost)
            if boost:
                await ctx.send('Bass boost turned on')
            else:
                await ctx.send('Bass boost turned off')

    @commands.command(name='shuffle')
    async def _shuffle(self, ctx):
        """ Shuffles your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        user_queue = player.user_queue(ctx.author.id)

        if not user_queue:
            return await ctx.send('Your queue is empty')

        player.shuffle_user_queue(ctx.author.id)
        await ctx.send('Your queue has been shuffled')

    @commands.command(name='move', aliases=["m"])
    async def _move(self, ctx, from_pos: int, to_pos: int):
        """ Moves a song in your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        user_queue = player.user_queue(ctx.author.id)
        if not user_queue:
            return await ctx.send('Your queue is empty')

        if not all(x in range(1,len(user_queue)+1) for x in [from_pos, to_pos]):
            return await ctx.send(f'Positions must be between 1 and {len(user_queue)}')

        moved = player.move_user_track(ctx.author.id, from_pos - 1, to_pos - 1)
        if moved is None:
            return await ctx.send('Check that the positions exist in your queue')
        
        await ctx.send(f'{moved.title} moved from position {from_pos} to {to_pos} in your queue')

    @commands.command(name='remove')
    async def _remove(self, ctx, pos: int):
        """ Removes the song at pos from your queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if player.queue.is_empty():
            return

        user_queue = player.user_queue(ctx.author.id)
        if not user_queue:
            return

        if pos > len(user_queue) or pos < 1:
            return await ctx.send(f'Position has to be between 1 and {len(user_queue)}')

        removed = player.remove_user_track(ctx.author.id, pos - 1)

        await ctx.send(f'**{removed.title}** removed.')

    @commands.command(name="DJremove")
    @checks.is_DJ()
    async def _djremove(self, ctx, pos: int, user: discord.Member=None):
        """ Remove a song from either the global queue or a users queue"""
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if user is None:
            if player.queue.is_empty():
                return

            if pos > len(player.queue) or pos < 1:
                return await ctx.send(f'Position has to be between 1 and {len(player.queue)}')

            removed = player.remove_global_track(pos - 1)
            requester = self.bot.get_user(removed.requester)
            await ctx.send(f'**{removed.title}** queued by {requester.name} removed.')

        else:
            if player.queue.is_empty():
                return

            user_queue = player.user_queue(user.id)
            if not user_queue:
                return

            if pos > len(user_queue) or pos < 1:
                return await ctx.send(f'Position has to be between 1 and {len(user_queue)}')

            removed = player.remove_user_track(user.id, pos - 1)
            await ctx.send(f'**{removed.title}** queued by {user.name} removed.')


    @commands.command(name='find')
    async def _find(self, ctx, *, query):
        """ Lists the first 10 search results from a given query. """
        await ctx.trigger_typing()
        not_reacted = True
        react_emoji = {1: "\u0030\u20E3", 2: "\u0031\u20E3", 3: "\u0032\u20E3", 4: "\u0033\u20E3", 5: "\u0034\u20E3",
                       6: "\u0035\u20E3", 7: "\u0036\u20E3", 8: "\u0037\u20E3", 9: "\u0038\u20E3", 10: "\u0039\u20E3"}

        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await self.bot.lavalink.get_tracks(query)

        if not results or not results['tracks']:
            return await ctx.send('Nothing found')

        tracks = results['tracks'][:10]  # First 10 results

        o = ''
        for index, track in enumerate(tracks, start=1):
            track_title = track["info"]["title"]
            track_uri = track["info"]["uri"]

            o += f'{react_emoji[index]} [{track_title}]({track_uri})\n'

        embed_start = discord.Embed(color=0xEFD26C, description=o)
        start_msg = await ctx.send(embed=embed_start)
        await ctx.trigger_typing()
        for num_index in range(min(len(tracks), 10)):
            index = num_index + 1
            await start_msg.add_reaction(react_emoji[index])
        await start_msg.add_reaction("\u274C")
        # React does shit
        time_start = time.time()

        while not_reacted:
            await ctx.trigger_typing()
            embed = discord.Embed(color=0xEFD26C)
            timer = time.time() - time_start
            msg_id = await ctx.get_message(start_msg.id)
            if int(timer) >= 10:
                await start_msg.clear_reactions()
                embed.title = "Sorry"
                embed.description = "Timer expired"
                await start_msg.edit(embed=embed)
                ping = await ctx.send(content=f"{ctx.author.mention}")
                await asyncio.sleep(10)
                await ctx.message.delete()
                await ping.delete()
                await msg_id.delete()
                break
            for react in msg_id.reactions:
                async for user in react.users():
                    if user is ctx.author:
                        if react.emoji[:-1].isdigit():
                            not_reacted = False
                            track_num = int(react.emoji[:-1])
                            track_ = tracks[track_num]
                            await self.send_to_play(ctx, track_)
                            embed.title = "Song sent to queue"
                            thumb_url = await RoxUtils.ThumbNailer.identify(self, track_['info']['identifier'],track_['info']['uri'])
                            if thumb_url:
                                embed.set_thumbnail(url=thumb_url)
                            embed.description = f'[{track_["info"]["title"]}]({track_["info"]["uri"]})'
                            await start_msg.edit(embed=embed)
                            await start_msg.clear_reactions()
                            break
                        if react.emoji == "\u274C":
                            not_reacted = False
                            await start_msg.clear_reactions()
                            embed.title = "Sorry"
                            embed.description = "Search cancelled by user"
                            await start_msg.edit(embed=embed)
                            ping = await ctx.send(content=f"{user.mention}")
                            await asyncio.sleep(10)
                            await ctx.message.delete()
                            await ping.delete()
                            await msg_id.delete()
                            break

    @commands.command(name='disconnect', aliases=['dc'])
    async def _disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_connected:
            return await ctx.send('Not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            return await ctx.send('You\'re not in my voicechannel!')

        player.queue.clear()
        await player.disconnect()
        await ctx.send('*⃣ | Disconnected.')

    async def send_to_play(self, ctx, track):
        await self.ensure_voice_real(ctx)
        player = self.bot.lavalink.players.get(ctx.guild.id)
        player.add(requester=ctx.author.id, track=track)
        if not player.is_playing:
            await player.play()

    @_playnow.before_invoke
    @_play.before_invoke
    async def ensure_voice(self, ctx):
        await self.ensure_voice_real(ctx)

    async def ensure_voice_real(self, ctx):
        """ A few checks to make sure the bot can join a voice channel. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_connected:
            if not ctx.author.voice or not ctx.author.voice.channel:
                await ctx.send('You aren\'t connected to any voice channel.')
                raise commands.CommandInvokeError(
                    'Author not connected to voice channel.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                await ctx.send('Missing permissions `CONNECT` and/or `SPEAK`.')
                raise commands.CommandInvokeError(
                    'Bot has no permissions CONNECT and/or SPEAK')

            player.store('channel', ctx.channel.id)
            await player.connect(ctx.author.voice.channel.id)

            # Get listeners
            voice_channel = ctx.author.voice.channel
            while not player.is_connected:
                await asyncio.sleep(1)

            for member in voice_channel.members:
                if not member.bot:
                    player.update_listeners(member, member.voice)


        else:
            if player.connected_channel.id != ctx.author.voice.channel.id:
                return await ctx.send('Join my voice channel!')


    async def on_voice_state_update(self, member, before, after):
        if not member.bot:
            if after.channel is not None:
                player = self.bot.lavalink.players.get(after.channel.guild.id)
                player.update_listeners(member, after)
            else:
                player = self.bot.lavalink.players.get(before.channel.guild.id)
                player.update_listeners(member)


def setup(bot):
    bot.add_cog(Music(bot))
