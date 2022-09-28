# Discord Packages
import discord
import lavalink
from lavalink import AudioTrack, DefaultPlayer, Node
from lavalink.events import QueueEndEvent, TrackEndEvent, TrackExceptionEvent, TrackStartEvent, TrackStuckEvent

import typing

from .mixqueue import MixQueue


class MixPlayer(DefaultPlayer):
    def __init__(self, guild_id: int, node: Node):
        super().__init__(guild_id, node)

        self.queue = MixQueue()

        self.listeners = set()
        self.voteables = {}
        self.skip_voters = set()
        self.boosted = False

    def add(self, requester: int, track: typing.Union[dict, AudioTrack], pos: int = None):
        """ Adds a track to the queue. """
        return self.queue.add_track(requester, track, pos)

    def add_next(self, requester: int, track: typing.Union[dict, AudioTrack], pos: int = None):
        """ Adds a track to beginning of the queue """
        self.queue.add_next_track(track)

    def move_user_track(self, requester: int, initial: int, final: int):
        """ Moves a track in a users queue"""
        return self.queue.move_user_track(requester, initial, final)

    def remove_user_queue(self, requester: int):
        self.queue.remove_user_queue(requester)

    def remove_user_track(self, requester: int, pos: int):
        """ Removes the song at <pos> from the queue of requester """
        return self.queue.remove_user_track(requester, pos)

    def remove_global_track(self, pos: int):
        """ Removes the song at <pos> in the global queue """
        return self.queue.remove_global_track(pos)

    def shuffle_user_queue(self, requester: int):
        """ Randomly reorders the queue of requester """
        self.queue.shuffle_user_queue(requester)

    def user_queue(self, user: int, dual: bool = False):
        return self.queue.get_user_queue(user, dual)

    def global_queue(self):
        return self.queue.get_queue()

    def get_history(self):
        return self.queue.history

    def queue_duration(self, include_current: bool = False, member: discord.Member = None, end_pos: int = None):
        duration = 0
        queue = self.user_queue(member.id) if member else self.queue

        for i, track in enumerate(queue):
            if i == end_pos:
                break
            duration += int(track.duration)

        remaining = self.current.duration - self.position
        if include_current:
            if self.current:
                remaining = self.current.duration - self.position
                return lavalink.utils.format_time(duration + remaining)
        return lavalink.utils.format_time(duration)

    async def play(self, track: AudioTrack = None, start_time: int = 0):

        self.current = None
        self.last_update = 0
        self.last_position = 0
        self.position_timestamp = 0
        self.paused = False

        if not track:
            if self.queue.empty:
                self.boosted = False
                await self.stop()
                await self.node._dispatch_event(QueueEndEvent(self))
                return
            else:
                track = self.queue.pop_first()

        self.current = track
        if track.track is None:
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
        if self.is_connected:
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
        for category, votes in self.voteables.items():
            votes.discard(member)

    def get_voters(self, category):
        if category not in self.voteables:
            self.voteables[category] = set()
        return self.voteables[category]

    def clear_votes(self):
        for category, votes in self.voteables.items():
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
            for category, votes in self.voteables.items():
                votes.clear()
            await self.play()

    async def bassboost(self, boost: bool = False):
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

    @property
    def looping(self):
        return self.queue.looping
