import time
import lavalink
from lavalink.events import (TrackStartEvent, TrackStuckEvent, TrackExceptionEvent, TrackEndEvent, QueueEndEvent, PlayerUpdateEvent,
                     NodeChangedEvent)
from lavalink import Node, DefaultPlayer, AudioTrack

from .mixqueue import MixQueue

class MixPlayer(DefaultPlayer):
    def __init__(self, guild_id: int, node: Node):
        super().__init__(guild_id, node)
        
        self.queue = MixQueue()
        
        self.listeners = set()
        self.skip_voters = set()
        self.boosted = False


    def add(self, requester: int, track: dict, pos: int=None):
        """ Adds a track to the queue. """
        return self.queue.add_track(requester, AudioTrack.build(track, requester), pos)

    def add_next(self, requester: int, track: dict):
        """ Adds a track to beginning of the queue """
        self.queue.add_next_track(AudioTrack.build(track, requester))

    def move_user_track(self, requester: int, initial: int, final: int):
        """ Moves a track in a users queue"""
        return self.queue.move_user_track(requester, initial, final)

    def remove_user_track(self, requester: int, pos: int):
        """ Removes the song at <pos> from the queue of requester """
        return self.queue.remove_user_track(requester, pos)

    def remove_global_track(self, pos: int):
        """ Removes the song at <pos> in the global queue """
        return self.queue.remove_global_track(pos)

    def shuffle_user_queue(self, requester: int):
        """ Randomly reorders the queue of requester """
        self.queue.shuffle_user_queue(requester)

    def user_queue(self, user: int, dual: bool=False):
        return self.queue.get_user_queue(user, dual)

    def global_queue(self):
        return self.queue.get_queue()

    def queue_duration(self, include_current: bool=True):
        duration = 0
        for track in self.queue:
            duration += track.duration
        remaining = self.current.duration - self.position
        if include_current:
            return lavalink.Utils.format_time(duration + remaining)
        return lavalink.Utils.format_time(duration)

    async def play(self, track: AudioTrack = None, start_time: int = 0):

        self.current = None
        self.last_update = 0
        self.last_position = 0
        self.position_timestamp = 0
        self.paused = False

        if not track:
            if self.queue.empty:
                await self.stop()
                await self.node._dispatch_event(QueueEndEvent(self))
                return
            else:
                track = self.queue.pop_first()

        self.current = track
        await self.node._send(op='play', guildId=self.guild_id, track=track.track, startTime=start_time)
        await self.node._dispatch_event(TrackStartEvent(self, track))

    async def skip(self, pos: int=0):
        """ Plays the next track in the queue, if any. """
        for i in range(pos):
            _ = self.queue.pop_first()
        self.skip_voters.clear()
        await self.play()

    async def handle_event(self, event):
        """ Handles the given event as necessary. """
        if isinstance(event, (TrackStuckEvent, TrackExceptionEvent)) or \
                isinstance(event, TrackEndEvent) and event.reason == 'FINISHED':
            await self.play()

    def update_listeners(self, member, voice_state):
        if self.is_connected:
            vc = int(self.channel_id)
            if voice_state.channel is None or voice_state.channel.id != vc:
                self.listeners.discard(member)
                self.skip_voters.discard(member)
            else:
                if voice_state.deaf or voice_state.self_deaf:
                    self.listeners.discard(member)
                    self.skip_voters.discard(member)
                else:
                    self.listeners.add(member)

    def add_skipper(self, member):
        if member in self.listeners:
            self.skip_voters.add(member)

    async def bassboost(self, boost: bool=False):
        if boost:
            gains = [
                (0, 0.15),
                (1, 0.15),
                (2, 0.25),
                (3, 0.15),
                (4, -0.15),
                (5, -0.1),
                (6, -0.05)
            ]
            self.boosted = True
            await self.set_gains(*gains)
        else:
            self.boosted = False
            await self.reset_equalizer()

