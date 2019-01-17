"""
This is an example cog that shows how you would make use of Lavalink.py.
This example cog requires that you have python 3.6 or higher due to the f-strings.
"""
import math
import re
import asyncio

import discord
import lavalink
from discord.ext import commands
import time

from .utils import checks, RoxUtils
from .utils.mixplayer import MixPlayer
from typing import Optional

from .utils.embedscroller import QueueScroller
from lavasettings import *

time_rx = re.compile('[0-9]+')
url_rx = re.compile('https?:\\/\\/(?:www\\.)?.+')


class Music:
    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            bot.lavalink = lavalink.Client(bot.user.id, player=MixPlayer)
            bot.lavalink.add_node(host, port, password, region, 'default-node')  # Host, Port, Password, Region, Name
            bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')

        bot.lavalink.add_event_hook(self.track_hook)

    def __unload(self):
        self.bot.lavalink._event_hooks.clear()

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.TrackEndEvent):
            pass  # Send track ended message to channel.
        if isinstance(event, lavalink.events.QueueEndEvent):
            channel = self.bot.get_channel(event.player.fetch('channel'))
            await self.check_leave_voice(channel.guild)

    async def __before_invoke(self, ctx):
        guild_check = ctx.guild is not None
        #  This is essentially the same as `@commands.guild_only()`
        #  except it saves us repeating ourselves (and also a few lines).

        if guild_check:
            await self.ensure_voice(ctx)
            #  Ensure that the bot and command author share a mutual voicechannel.

        return guild_check

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        results = await player.node.get_tracks(query)

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
            # Rox
            thumbnail_url = await RoxUtils.ThumbNailer.identify(self, track['info']['identifier'], track['info']['uri'])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
            await ctx.send(embed=embed)
            player.add(requester=ctx.author.id, track=track)

        if not player.is_playing:
            await player.play()

    @commands.command()
    @checks.DJ_or_alone()
    async def seek(self, ctx, *, time: str):
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

        await ctx.send(f'Moved track to **{lavalink.utils.format_time(track_time)}**')

    @commands.command(aliases=['forceskip'])
    async def skip(self, ctx):
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

    @commands.command(name='skipto', aliases=['st','skip_to'])
    @checks.DJ_or_alone()
    async def skip_to(self, ctx, pos: int):
        """ Plays the queue from a specific point. Disregards tracks before the pos. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if ctx.author not in player.listeners:
            return await ctx.send('You have to be listening to the bot')

        if pos < 1:
            return await ctx.send('Invalid specified position.')
        if len(player.queue) < pos:
            return await ctx.send('The position exceeds the queue\'s length.')
        await player.skip(pos - 1)

    @commands.command()
    @checks.DJ_or_alone()
    async def stop(self, ctx):
        """ Stops the player and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if ctx.author not in player.listeners:
            return await ctx.send('You have to be listening to the bot')

        if not player.is_playing:
            return await ctx.send('Not playing.')

        player.queue.clear()
        await player.stop()
        await ctx.send('⏹ | Stopped.')

    @commands.command(aliases=['np', 'n', 'playing'])
    async def now(self, ctx):
        """ Shows some stats about the currently playing song. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.current:
            return await ctx.send('Nothing playing.')

        position = lavalink.utils.format_time(player.position)
        if player.current.stream:
            duration = '🔴 LIVE'
        else:
            duration = lavalink.utils.format_time(player.current.duration)
        song = f'**[{player.current.title}]({player.current.uri})**\n({position}/{duration})'

        embed = discord.Embed(color=0xEFD26C,
                              title='Now Playing', description=song)

        thumbnail_url = await RoxUtils.ThumbNailer.identify(self,player.current.identifier, player.current.uri)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['q'])
    async def queue(self, ctx, user: discord.Member=None):
        """ Shows the player's queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if player.queue.empty:
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

    @commands.command(aliases=['resume'])
    @checks.is_DJ()
    async def pause(self, ctx):
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

    @commands.command(aliases=['vol'])
    @checks.is_DJ()
    async def volume(self, ctx, volume: int = None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not volume:
            return await ctx.send(f'🔈 | {player.volume}%')

        await player.set_volume(volume)
        await ctx.send(f'🔈 | Set to {player.volume}%')

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

    @commands.command()
    async def remove(self, ctx, pos: int):
        """ Removes an item from the player's queue with the given pos. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if player.queue.empty:
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
            if player.queue.empty:
                return

            if pos > len(player.queue) or pos < 1:
                return await ctx.send(f'Position has to be between 1 and {len(player.queue)}')

            removed = player.remove_global_track(pos - 1)
            requester = self.bot.get_user(removed.requester)
            await ctx.send(f'**{removed.title}** queued by {requester.name} removed.')

        else:
            if player.queue.empty:
                return

            user_queue = player.user_queue(user.id)
            if not user_queue:
                return

            if pos > len(user_queue) or pos < 1:
                return await ctx.send(f'Position has to be between 1 and {len(user_queue)}')

            removed = player.remove_user_track(user.id, pos - 1)
            await ctx.send(f'**{removed.title}** queued by {user.name} removed.')

    @commands.command()
    async def search(self, ctx, *, query):
        """ Lists the first 10 search results from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not query.startswith('ytsearch:') and not query.startswith('scsearch:'):
            query = 'ytsearch:' + query

        results = await player.node.get_tracks(query)

        embed = discord.Embed(description='Nothing found', color=0x36393F)
        if not results or not results['tracks']:
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

        embed.description = 'searching'
        result_msg = await ctx.send(embed=embed)

        for emoji, index in choices[:result_count]:
            await result_msg.add_reaction(emoji)
        await result_msg.add_reaction('❌')

        embed.description = search_results
        embed.title = 'Results'
        await result_msg.edit(embed=embed)

        try:
            reaction, user = await self.bot.wait_for('reaction_add',
                                                     timeout=15.0,
                                                     check=check)
        except asyncio.TimeoutError:
            await result_msg.clear_reactions()
            embed.title = ''
            embed.description='Timer Expired'
            await result_msg.edit(embed=embed)
            await asyncio.sleep(5)
            await result_msg.delete()
        else:
            if choice is None:
                await result_msg.delete()
            else:
                await result_msg.clear_reactions()
                track = tracks[choice - 1]
                info = track['info']
                embed.title = 'Song sent to queue'
                thumb_url = await RoxUtils.ThumbNailer.identify(self,
                                                                info['identifier'],
                                                                info['uri'])
                if thumb_url:
                    embed.set_thumbnail(url=thumb_url)
                embed.description = f'[{info["title"]}]({info["uri"]})'
                await result_msg.edit(embed=embed)

                player.add(requester=ctx.author.id, track=track)
                if not player.is_playing:
                    await player.play()

    @commands.command(aliases=['dc'])
    @checks.DJ_or_alone()
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_connected:
            return await ctx.send('Not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            return await ctx.send('You\'re not in my voicechannel!')

        player.queue.clear()
        await player.stop()
        await self.connect_to(ctx.guild.id, None)
        embed = discord.Embed(description='Disconnected', color=0x36393F)
        await ctx.send(embed=embed)

    @commands.command(name='boost', aliases=['boo'])
    @checks.DJ_or_alone()
    async def _boost(self, ctx, boost: bool=None):
        """ Changes the player's volume. Must be between 0 and 1000. Error Handling for that is done by Lavalink. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        
        if boost is not None:
            await player.bassboost(boost)

        embed = discord.Embed(color=0x36393F)

        if player.boosted:
            embed.description = 'Bass boost is on'
            await ctx.send(embed=embed)
        else:
            embed.description = 'Bass boost is off'
            await ctx.send(embed=embed)

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

            # Get listeners
            voice_channel = ctx.author.voice.channel
            while not player.is_connected:
                await asyncio.sleep(1)

            for member in voice_channel.members:
                if not member.bot:
                    player.update_listeners(member, member.voice)

        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You need to be in my voicechannel.')

    async def on_voice_state_update(self, member, before, after):
        if not member.bot:
            player = self.bot.lavalink.players.get(member.guild.id)
            if player is not None:
                player.update_listeners(member, after)
                await self.check_leave_voice(member.guild)

    async def check_leave_voice(self, guild):
        player = self.bot.lavalink.players.get(guild.id)
        if len(player.listeners) == 0 and player.is_connected:
            if player.queue.empty and player.current is None:
                await player.stop()
                await self.connect_to(guild.id, None)


def setup(bot):
    bot.add_cog(Music(bot))
