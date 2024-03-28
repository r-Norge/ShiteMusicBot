import logging
from typing import Dict, List, Optional, Set, Tuple

import discord
import lavalink
from lavalink import AudioTrack, DefaultPlayer, Node
from lavalink.events import QueueEndEvent, TrackEndEvent, TrackExceptionEvent, TrackStartEvent, TrackStuckEvent
from lavalink.filters import Equalizer, Timescale

from .mixqueue import MixQueue

RequesterType = discord.Member


class MixPlayer(DefaultPlayer):
    def __init__(self, guild_id: int, node: Node):
        super().__init__(guild_id, node)

        self.queue: MixQueue[AudioTrack] = MixQueue()

        self.listeners: Set[RequesterType] = set()
        self.voteables: Dict[int, Set[RequesterType]] = {}
        self.skip_voters: Set[int] = set()
        self.boosted: bool = False
        self.nightcore_enabled: bool = False
        self.logger = logging.getLogger("musicbot").getChild("MixPlayer")
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

    def add(self, requester: RequesterType, track: AudioTrack,
            pos: Optional[int] = None) -> Tuple[AudioTrack, int, int]:
        """Adds a track to the queue."""
        track, global_position, localpos = self.queue.add_track(requester.id, track, pos)
        self.logger.info(f"Track {track.title} added for {requester.display_name} @ ({global_position}, {localpos}).")
        return track, global_position, localpos

    def add_priority(self, track: AudioTrack):
        """Adds a track to beginning of the queue."""
        self.queue.add_priorty_queue_track(track)
        self.logger.info(f"Track {track} added to priority queue.")

    def move_user_track(self, requester: RequesterType, initial: int, final: int):
        """Moves a track in a users queue."""
        if moved := self.queue.move_user_track(requester.id, initial, final):
            self.logger.info(f"Track {moved.title} moved from {initial} to {final}" +
                             f"for in queue for {requester.display_name}")

    def remove_user_queue(self, requester: RequesterType):
        removed = self.queue.remove_user_queue(requester.id)
        if removed:  # Removed queues can be empty
            self.logger.info(f"Queue for requester {requester.display_name} removed. {len(removed)} tracks removed")
        else:
            self.logger.debug(f"User {requester.display_name} has no more tracks. Remove from queue")

    def remove_user_track(self, requester: RequesterType, pos: int) -> Optional[AudioTrack]:
        """Removes the song at <pos> from the queue of requester."""
        if track := self.queue.remove_user_track(requester.id, pos):
            self.logger.info(f"Track {track.title} for requester {requester.display_name} removed.")
            return track

    def remove_track(self, track: AudioTrack) -> Optional[Tuple[int, AudioTrack]]:
        return self.queue.remove_track(track)

    def remove_global_track(self, pos: int) -> Optional[AudioTrack]:
        """Removes the song at <pos> in the global queue."""
        return self.queue.remove_global_track(pos)

    def shuffle_user_queue(self, requester: RequesterType):
        """Randomly reorders the queue of requester."""
        self.queue.shuffle_user_queue(requester.id)

    def user_queue(self, requester: RequesterType) -> List[AudioTrack]:
        return self.queue.get_user_queue(requester.id)

    def user_queue_with_global_index(self, requester: RequesterType) -> List[Tuple[AudioTrack, int]]:
        return self.queue.get_user_queue_with_index(requester.id)

    def global_queue(self) -> List[AudioTrack]:
        return self.queue.get_queue()

    def get_history(self) -> List[AudioTrack]:
        return self.queue.history

    def queue_duration(self, include_current: bool = False,
                       member: Optional[RequesterType] = None, end_pos: Optional[int] = None):
        duration = 0
        queue = self.user_queue(member) if member else self.queue

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
                self.logger.debug("No track provided to play function and queue is empty. Resetting Audio filters")
                await self.bassboost(False)
                await self.nightcoreify(False)
                await self.stop()
                await self.client._dispatch_event(QueueEndEvent(self))
                return
            else:
                # At this point track will not be None, as the queue is not empty
                track = self.queue.pop_first()

        self.current = track
        if track is None or track.track is None:
            # Ignore, if the queue was empty we would have dispatched the event already
            return
        await self.play_track(track, start_time)

        await self.client._dispatch_event(TrackStartEvent(self, track))
        self.logger.info(f"Playing track: {track.title}")

    async def skip(self, pos: int = 0):
        """Plays the next track in the queue, if any."""
        for _ in range(pos):
            track = self.queue.pop_first()
            self.logger.debug(f"Track {track} skipped")
        self.logger.info(f"Skipped {pos + 1} tracks")
        self.clear_votes()
        await self.play()

    async def stop(self):
        """Stops the player."""
        # await self.node._send(op='stop', guildId=str(self.guild_id))
        await super().stop()
        self.current = None
        self.queue.enable_looping(False)
        self.logger.info("Music player stopped, clearing current track and stopping looping")
        self.clear_votes()

    def update_listeners(self, member: RequesterType, voice_state):
        if self.channel_id is not None:
            vc = int(self.channel_id)
            if voice_state.channel is None or voice_state.channel.id != vc:
                self.logger.debug(f"User {member.display_name} left the voice channel")
                self.listeners.discard(member)
                self.remove_member_votes(member)
            else:
                if voice_state.deaf or voice_state.self_deaf:
                    self.logger.debug(f"User {member.display_name} is now deafened")
                    self.listeners.discard(member)
                    self.remove_member_votes(member)
                else:
                    self.listeners.add(member)
            self.logger.debug(f"Member voice state update. Votes are now {self.voteables}")

    def clear_listeners(self):
        self.logger.debug("Listeners cleared")
        self.listeners.clear()

    def add_vote(self, category, member: RequesterType):
        if member in self.listeners:
            if category not in self.voteables:
                self.voteables[category] = set()
            self.voteables[category].add(member)
            self.logger.debug(f"{member.display_name} added vote for {category}")

    def remove_member_votes(self, member: RequesterType):
        for _, votes in self.voteables.items():
            votes.discard(member)
        self.logger.debug(f"Removing votes for {member.display_name}.")

    def get_voters(self, category) -> Set[RequesterType]:
        if category not in self.voteables:
            self.voteables[category] = set()
        return self.voteables[category]

    def clear_votes(self):
        for _, votes in self.voteables.items():
            votes.clear()

    def enable_looping(self, looping: bool):
        if (not self.queue.looping) and looping:
            self.queue.enable_looping(looping)
            if track := self.current:
                if looping:
                    self.queue.add_track(track.requester, track)
        elif not looping and self.queue.looping:
            self.queue.enable_looping(looping)

    async def handle_event(self, event):
        """Handles the given event as necessary."""
        if isinstance(event, (TrackStuckEvent, TrackExceptionEvent)) or \
                isinstance(event, TrackEndEvent) and event.reason == 'FINISHED':
            self.logger.debug("Track ended, clearing votes")
            self.skip_voters.clear()
            for _, votes in self.voteables.items():
                votes.clear()
            await self.play()

    async def bassboost(self, boost: bool):
        changed = self.boosted != boost
        self.boosted = boost
        if changed:
            self.logger.info(f"{'Enabling' if self.boosted else 'Disabling'} bass boost")
        if boost:
            await self.set_filter(self.bass_boost_filter)
        else:
            await self.remove_filter(self.bass_boost_filter)

    async def nightcoreify(self, nightcore: bool):
        changed = self.nightcore_enabled != nightcore
        self.nightcore_enabled = nightcore
        if changed:
            self.logger.info(f"{'Enabling' if self.nightcore_enabled else 'Disabling'} nightcore mode")
        if nightcore:
            await self.set_filter(self.nightcore_filter)
        else:
            await self.remove_filter(self.nightcore_filter)

    @property
    def looping(self):
        return self.queue.looping
