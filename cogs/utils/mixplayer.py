import lavalink

from collections import OrderedDict, deque
from itertools import cycle, islice, chain
from random import shuffle

from lavalink.events import TrackStartEvent, TrackStuckEvent, TrackExceptionEvent, TrackEndEvent, QueueEndEvent
from lavalink import Node, DefaultPlayer, AudioTrack


class MixPlayer(DefaultPlayer):
    def __init__(self, guild_id: int, node: Node):
        super().__init__(guild_id, node)

        self.queue = MixQueue()

        self.listeners = set()
        self.skip_voters = set()
        self.boosted = False

    def add(self, requester: int, track: dict, pos: int = None):
        """ Adds a track to the queue. """
        return self.queue.add_track(requester, AudioTrack.build(track, requester), pos)

    def add_next(self, requester: int, track: dict):
        """ Adds a track to beginning of the queue """
        self.queue.add_next_track(AudioTrack.build(track, requester))

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

    def queue_duration(self, include_current: bool = True):
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
                self.boosted = False
                await self.stop()
                await self.node._dispatch_event(QueueEndEvent(self))
                return
            else:
                track = self.queue.pop_first()

        self.current = track
        await self.node._send(op='play', guildId=self.guild_id,
                              track=track.track, startTime=start_time)
        await self.node._dispatch_event(TrackStartEvent(self, track))

    async def skip(self, pos: int = 0):
        """ Plays the next track in the queue, if any. """
        for i in range(pos):
            _ = self.queue.pop_first()
        self.skip_voters.clear()
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

    def clear_listeners(self):
        self.listeners.clear()

    def add_skipper(self, member):
        if member in self.listeners:
            self.skip_voters.add(member)

    async def handle_event(self, event):
        """ Handles the given event as necessary. """
        if isinstance(event, (TrackStuckEvent, TrackExceptionEvent)) or \
                isinstance(event, TrackEndEvent) and event.reason == 'FINISHED':
            self.skip_voters.clear()
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


def roundrobin(*iterables):
    """roundrobin('ABC', 'D', 'EF') --> A D E B F C"""
    # Recipe credited to George Sakkis
    num_active = len(iterables)
    nexts = cycle(iter(it).__next__ for it in iterables)
    while num_active:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            num_active -= 1
            nexts = cycle(islice(nexts, num_active))


class MixQueue:
    def __init__(self):
        self.queues = OrderedDict()
        self.priority_queue = []
        self._history = deque(maxlen=11)  # 10 + current

    def __str__(self):
        tmp = ''
        for requester in self.queues.keys():
            user_queue = list(map(str, self.queues[requester]))
            tmp += f'{requester}: {user_queue}\n'
        return tmp

    def __bool__(self):
        return not self.empty

    def __iter__(self):
        global_queue = roundrobin(*[x for x in self.queues.values()])
        priority_queue = self.priority_queue
        out = chain(priority_queue, global_queue)
        return out

    def __len__(self):
        length = 0
        for _ in self:
            length += 1
        return length

    def get_queue(self):
        return list(self)

    def clear(self):
        self.queues = OrderedDict()
        self.priority_queue = []

    # if dual is true also returns global positions of tracks
    def get_user_queue(self, requester: int, dual: bool = False):
        queue = self.queues.get(requester, [])
        if dual and queue:
            pos = [self._loc_to_glob(requester, i) for i in range(len(queue))]
            combined = zip(queue, pos)
            return list(combined)
        return queue

    def pop_first(self):
        if self.priority_queue:
            next_track = self.priority_queue.pop(0)
            self._history.append(next_track)
            return next_track
        try:
            next_track = self.queues[self.first_queue].pop(0)
            self._shuffle()
            self._clear_empty()
            self._history.append(next_track)
            return next_track
        except KeyError:
            pass

    def add_track(self, requester: int, track: AudioTrack, pos: int = None):
        user_queue = self.queues.get(requester)
        if user_queue is None:
            self.queues[requester] = [track]
            localpos = 0
        elif pos is None:
            user_queue.append(track)
            localpos = len(user_queue) - 1
        else:
            user_queue.insert(pos, track)
            localpos = pos

        # Return info about track position
        return track, self._loc_to_glob(requester, localpos), localpos

    def add_next_track(self, track: AudioTrack):
        self.priority_queue.append(track)

    def remove_user_queue(self, requester: int):
        user_queue = self.queues.get(requester, [])
        if user_queue:
            self.queues.pop(requester)

    def remove_user_track(self, requester: int, pos: int):
        user_queue = self.queues.get(requester)
        if user_queue is not None:
            if pos < len(user_queue):
                track = user_queue.pop(pos)
                self._clear_empty()
                return track

    def remove_global_track(self, pos: int):
        q, pos = self._glob_to_loc(pos)
        if q is None or pos is None:
            return
        queue = self.queues.get(q)
        track = queue.pop(pos)
        self._clear_empty()
        return track

    def move_user_track(self, requester: int, initial: int, final: int):
        queue = self.queues.get(requester, [])
        if queue:
            try:
                track = queue.pop(initial)
                queue.insert(final, track)
                return track
            except IndexError:
                pass

    def shuffle_user_queue(self, requester: int):
        queue = self.queues.get(requester, [])
        if queue:
            shuffle(queue)

    # Switches the order of user queues
    def _shuffle(self):
        self.queues.move_to_end(self.first_queue)

    # Removes empty user queues
    def _clear_empty(self):
        to_remove = [q for q in reversed(self.queues) if not self.queues[q]]
        for i in to_remove:
            self.queues.pop(i)

    def _loc_to_glob(self, requester, pos):
        globpos = len(self.priority_queue)
        passed = False
        for key, queue in self.queues.items():
            if len(queue) <= pos:
                globpos += len(queue)
            else:
                globpos += pos
                if key == requester:
                    passed = True
                if not passed:
                    globpos += 1
        return globpos

    def _glob_to_loc(self, pos: int):
        try:
            song = next(islice(self, pos, pos + 1))
        except (ValueError, StopIteration):
            return None, None
        user_queue = self.queues.get(song.requester, [])

        # In case song is in the priority queue
        if not user_queue or song not in user_queue:
            return None, pos

        for i, s in enumerate(user_queue):
            if s == song:
                return song.requester, i

    @property
    def first_queue(self):
        try:
            return list(self.queues.keys())[0]
        except IndexError:
            pass

    @property
    def empty(self):
        return len(self) == 0

    @property
    def history(self):
        return list(reversed(self._history))
