"""
A cog to separate events from regular music commands
"""

import codecs
import yaml
import lavalink
from discord.ext import commands

from .utils.mixplayer import MixPlayer
import lavalink.events


class MusicEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # TODO: maybe only load when Music loads
        if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            bot.lavalink = lavalink.Client(bot.user.id, player=MixPlayer)

            with codecs.open(f"{self.bot.datadir}/config.yaml", 'r', encoding='utf8') as f:
                conf = yaml.load(f, Loader=yaml.SafeLoader)

            bot.lavalink.add_node(**conf['lavalink nodes']['main'])
            bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')

        lavalink.add_event_hook(self.track_hook)

    def cog_unload(self):
        self.bot.lavalink._event_hooks.clear()

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.TrackEndEvent):
            pass  # Send track ended message to channel.
        if isinstance(event, lavalink.events.TrackStartEvent):
            pass
        if isinstance(event, lavalink.events.QueueEndEvent):
            channel = self.bot.get_channel(event.player.fetch('channel'))
            await self.check_leave_voice(channel.guild)
        if isinstance(event, lavalink.events.PlayerUpdateEvent):
            pass
        if isinstance(event, lavalink.events.NodeDisconnectedEvent):
            pass
        if isinstance(event, lavalink.events.NodeConnectedEvent):
            pass
        if isinstance(event, lavalink.events.NodeChangedEvent):
            pass

    async def connect_to(self, guild_id: int, channel_id: str):
        """ Connects to the given voicechannel ID. A channel_id of `None` means disconnect. """
        ws = self.bot._connection._get_websocket(guild_id)
        await ws.voice_state(str(guild_id), channel_id)

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
                await self.connect_to(guild.id, None)


def setup(bot):
    bot.add_cog(MusicEvents(bot))
