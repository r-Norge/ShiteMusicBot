# Discord Packages
import discord

from bot import MusicBot
from musicbot.cogs.music.music_errors import MusicError


class BasicVoiceClient(discord.VoiceClient):
    def __init__(self, client: MusicBot, channel: discord.VoiceChannel):
        # Needs to be named client in order for base class to work
        # in most cases lavalink handles disconnects, but if we force it then we'll get an error.
        # during self.cleanup()
        self.client = client
        self.channel = channel
        if self.client.lavalink:
            self.lavalink = self.client.lavalink
        else:
            raise MusicError("client did not have defined lavalink before connect")

    async def on_voice_server_update(self, data):
        await self.lavalink.voice_update_handler({'t': 'VOICE_SERVER_UPDATE', 'd': data})

    async def on_voice_state_update(self, data):
        await self.lavalink.voice_update_handler({'t': 'VOICE_STATE_UPDATE', 'd': data})

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = False,
                      self_mute: bool = False) -> None:
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)

    async def disconnect(self, *, force: bool = False) -> None:
        player = self.lavalink.player_manager.get(self.channel.guild.id)

        if player:
            # no need to disconnect if we are not connected
            if not force and not player.is_connected:
                return

            # None means disconnect
            await self.channel.guild.change_voice_state(channel=None)
            player.channel_id = None
            self.cleanup()
