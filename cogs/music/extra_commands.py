"""
Commands that add to the music bot experience, like equalizers, commands that access the web, like lyrics, and
commands that are complex and mostly for show, like scrubber.
"""

# Discord Packages
import discord
from discord.ext import commands

import asyncio
import json
import re
import urllib

from bs4 import BeautifulSoup

from ..helpformatter import commandhelper
from ..utils import checks
from ..utils.paginator import Scroller, TextPaginator
from .decorators import require_playing, require_voice_connection, voteable


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

    if boost is not None:
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
            except (discord.Forbidden, discord.HTTPException):
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


@commands.group(name='loop')
async def _loop(self, ctx):
    # This is done using subcommands to have separate vote counts for starting and stopping.
    if ctx.invoked_subcommand is None:
        ctx.localizer.prefix = 'help'  # Ensure the bot looks for locales in the context of help, not cogmanager.
        paginator = commandhelper(ctx, ctx.command, ctx.invoker, include_subcmd=True)
        scroller = Scroller(ctx, paginator)
        await scroller.start_scrolling()


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
