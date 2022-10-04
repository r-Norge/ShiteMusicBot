# Discord Packages
import discord
import lavalink
from lavalink import AudioTrack, DefaultPlayer, Node
from lavalink.events import QueueEndEvent, TrackEndEvent, TrackExceptionEvent, TrackStartEvent, TrackStuckEvent
from lavalink.filters import Equalizer, Timescale

from typing import Dict, List, Optional, Set, Tuple

from .mixqueue import MixQueue


class MixPlayer(DefaultPlayer):
    def __init__(self, guild_id: int, node: Node):
        super().__init__(guild_id, node)

        self.queue: MixQueue[AudioTrack] = MixQueue()

        self.listeners: Set[int] = set()
        self.voteables: Dict[int, Set[int]] = {}
        self.skip_voters: Set[int] = set()
        self.boosted: bool = False
        self.nightcore_enabled: bool = False
        bands = [
            (0, 0.15),
            (1, 0.15),
            (2, 0.25),
            (3, 0.15),
            (4, -0.15),
            (5, -0.1),
            (6, -0.05)
        ]
        self.bass_boost_filter: lavalink.Filter = Equalizer()
        self.bass_boost_filter.update(bands=bands)

        self.nightcore_filter: lavalink.Filter = Timescale()
        self.nightcore_filter.update(speed=1.25, pitch=1.25)

    def add(self, requester: int, track: AudioTrack, pos: Optional[int] = None) -> Tuple[AudioTrack, int, int]:
        """ Adds a track to the queue. """
        return self.queue.add_track(requester, track, pos)

    def add_priority(self, track: AudioTrack):
        """ Adds a track to beginning of the queue """
        self.queue.add_next_track(track)

    def move_user_track(self, requester: int, initial: int, final: int):
        """ Moves a track in a users queue"""
        return self.queue.move_user_track(requester, initial, final)

    def remove_user_queue(self, requester: int):
        self.queue.remove_user_queue(requester)

    def remove_user_track(self, requester: int, pos: int) -> Optional[AudioTrack]:
        """ Removes the song at <pos> from the queue of requester """
        return self.queue.remove_user_track(requester, pos)

    def remove_global_track(self, pos: int) -> Optional[AudioTrack]:
        """ Removes the song at <pos> in the global queue """
        return self.queue.remove_global_track(pos)

    def shuffle_user_queue(self, requester: int):
        """ Randomly reorders the queue of requester """
        self.queue.shuffle_user_queue(requester)

    def user_queue(self, user: int) -> List[AudioTrack]:
        return self.queue.get_user_queue(user)

    def user_queue_with_global_index(self, user: int) -> List[Tuple[AudioTrack, int]]:
        return self.queue.get_user_queue_with_index(user)

    def global_queue(self) -> List[AudioTrack]:
        return self.queue.get_queue()

    def get_history(self) -> List[AudioTrack]:
        return self.queue.history

    def queue_duration(self, include_current: bool = False,
                       member: Optional[discord.Member] = None, end_pos: Optional[int] = None):
        duration = 0
        queue = self.user_queue(member.id) if member else self.queue

        for i, track in enumerate(queue):
            if i == end_pos:
                break
            duration += int(track.duration)

        if include_current:
            if self.current:
                remaining = self.current.duration - int(self.position)
                return lavalink.utils.format_time(duration + remaining)
        return lavalink.utils.format_time(duration)

    async def play(self, track: Optional[AudioTrack] = None, start_time: int = 0):

        self.current = None
        self.last_update = 0
        self.last_position = 0
        self.position_timestamp = 0
        self.paused = False

        if not track:
            if self.queue.empty:
                self.boosted = False
                self.nightcore_enabled = False
                await self.stop()
                await self.node._dispatch_event(QueueEndEvent(self))
                return
            else:
                # At this point track will not be None, as the queue is not empty
                track = self.queue.pop_first()

        self.current = track
        if track is None or track.track is None:
            # Ignore, if the queue was empty we would have dispatched the event already
            return
        await self.node._send(op='play', guildId=str(self.guild_id),
                              track=track.track, startTime=start_time)
        await self.node._dispatch_event(TrackStartEvent(self, track))

    async def skip(self, pos: int = 0):
        """ Plays the next track in the queue, if any. """
        for i in range(pos):
            _ = self.queue.pop_first()
        self.clear_votes()
        await self.play()

    async def stop(self):
        """ Stops the player. """
        await self.node._send(op='stop', guildId=str(self.guild_id))
        self.current = None
        self.queue.looping = False
        self.clear_votes()

    def update_listeners(self, member, voice_state):
        if self.channel_id is not None:
            vc = int(self.channel_id)
            if voice_state.channel is None or voice_state.channel.id != vc:
                self.listeners.discard(member)
                self.remove_member_votes(member)
            else:
                if voice_state.deaf or voice_state.self_deaf:
                    self.listeners.discard(member)
                    self.remove_member_votes(member)
                else:
                    self.listeners.add(member)

    def clear_listeners(self):
        self.listeners.clear()

    def add_vote(self, category, member):
        if member in self.listeners:
            if category not in self.voteables:
                self.voteables[category] = set()
            self.voteables[category].add(member)

    def remove_member_votes(self, member):
        for _, votes in self.voteables.items():
            votes.discard(member)

    def get_voters(self, category):
        if category not in self.voteables:
            self.voteables[category] = set()
        return self.voteables[category]

    def clear_votes(self):
        for _, votes in self.voteables.items():
            votes.clear()

    def enable_looping(self, looping):
        if (not self.queue.looping) and looping:
            self.queue.enable_looping(looping)
            if track := self.current:
                if looping:
                    self.queue.add_track(track.requester, track)
        elif not looping and self.queue.looping:
            self.queue.enable_looping(looping)

    async def handle_event(self, event):
        """ Handles the given event as necessary. """
        if isinstance(event, (TrackStuckEvent, TrackExceptionEvent)) or \
                isinstance(event, TrackEndEvent) and event.reason == 'FINISHED':
            self.skip_voters.clear()
            for _, votes in self.voteables.items():
                votes.clear()
            await self.play()

    async def bassboost(self, boost: bool = False):
        self.boosted = boost
        if boost:
            await self.set_filter(self.bass_boost_filter)
        else:
            await self.remove_filter(self.bass_boost_filter)

    async def nightcoreify(self, nightcore: bool = False):
        self.nightcore_enabled = nightcore
        if nightcore:
            await self.set_filter(self.nightcore_filter)
        else:
            await self.remove_filter(self.nightcore_filter)

    @property
    def looping(self):
        return self.queue.looping
