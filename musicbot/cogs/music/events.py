
# Discord Packages
import lavalink
import lavalink.events
from discord.ext import commands, tasks


def cog_unload(self):
    self.bot.lavalink._event_hooks.clear()


async def track_hook(self, event):
    if isinstance(event, lavalink.events.TrackEndEvent):
        channel = self.bot.get_channel(event.player.fetch('channel'))
        player = self.bot.lavalink.player_manager.get(channel.guild.id)
        player.skip_voters.clear()

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
    if isinstance(event, lavalink.events.TrackStuckEvent):
        print(event)


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


async def leave_check(self):
    for player_id in self.bot.lavalink.player_manager.players:
        await self.check_leave_voice(self.bot.get_guild(player_id))


@tasks.loop(seconds=10.0)
async def leave_timer(self):
    try:
        await self.leave_check()
    except Exception as err:
        self.logger.debug("Error in leave_timer loop.\nTraceback: %s" % (err))
