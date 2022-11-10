# Discord Packages
from lavalink.models import AudioTrack

import logging
from collections import OrderedDict, deque
from itertools import chain, cycle, islice
from random import shuffle
from typing import Generic, Iterable, Iterator, List, Optional, Tuple, TypeVar

# Would like to ensure the T has a "requester" attribute, but don't know if that is possible
T = TypeVar('T', bound=AudioTrack)
QueueType = List[T]


def roundrobin(*iterables: Iterable[T]) -> Iterator[T]:
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


class MixQueue(Generic[T]):
    def __init__(self):
        self.queues: OrderedDict[int, QueueType] = OrderedDict()
        self.priority_queue: QueueType = []
        self._history = deque(maxlen=11)  # 10 + current
        self.looping = False
        self.loop_offset = 0
        self.logger = logging.getLogger("musicbot").getChild("Queue")

    def __str__(self) -> str:
        tmp = ''
        for requester in self.queues.keys():
            user_queue = list(map(str, self.queues[requester]))
            tmp += f'{requester}: {user_queue}\n'
        return tmp

    def __bool__(self) -> bool:
        return not self.empty

    def __iter__(self) -> Iterator[T]:
        global_queue = roundrobin(*[x for x in self.queues.values()])
        priority_queue = self.priority_queue
        out = chain(priority_queue, global_queue)
        return out

    def __len__(self) -> int:
        length = 0
        for _ in self:
            length += 1
        return length

    def get_queue(self) -> QueueType:
        if self.looping:
            offset = self.loop_offset
            return list(self)[offset:] + list(self)[:offset]
        else:
            return list(self)

    def clear(self) -> None:
        self.queues = OrderedDict()
        self.priority_queue = []
        self.looping = False
        self.loop_offset = 0

    # if dual is true also returns global positions of tracks
    def get_user_queue(self, requester: int) -> QueueType:
        return self.queues.get(requester, [])

    def get_user_queue_with_index(self, requester: int) -> List[Tuple[T, int]]:
        queue = self.queues.get(requester, [])
        pos = [self._loc_to_glob(requester, i) for i in range(len(queue))]
        if self.looping:
            pos = [(p + self.loop_offset) % len(self) for p in pos]
        combined = zip(queue, pos)
        return list(combined)

    def pop_first(self) -> Optional[T]:
        if self.priority_queue:
            next_track = self.priority_queue.pop(0)
            self._history.append(next_track)
            return next_track
        try:
            if self.looping:
                try:
                    queue = list(self)
                    next_track = queue[self.loop_offset]
                    self.loop_offset += 1
                    if self.loop_offset >= len(self):
                        self.loop_offset = 0
                    self._history.append(next_track)
                    return next_track
                except IndexError as e:
                    self.logger.error(f"Failed to get the next track in looping mode: loop offset {self.loop_offset}." +
                                      " Queue length: {len(self)}")
                    self.logger.exception(e)
                    self.loop_offset = min(self.loop_offset, len(self)-1)
            else:
                if first_queue := self.first_queue:
                    next_track = self.queues[first_queue].pop(0)
                    self._shift_queues()
                    self._clear_empty()
                    self._history.append(next_track)
                    return next_track
        except KeyError:
            pass

    def add_track(self, requester: int, track: T, pos: Optional[int] = None) -> Tuple[T, int, int]:
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
        global_position = self._loc_to_glob(requester, localpos)
        return track, global_position, localpos

    def add_priorty_queue_track(self, track: T) -> None:
        self.priority_queue.append(track)

    def remove_user_queue(self, requester: int) -> QueueType:
        user_queue = self.queues.get(requester, [])
        if user_queue:
            if self.looping:
                # Should work, kinda hacky.
                for pos, _ in reversed(list(enumerate(user_queue))):
                    self.remove_user_track(requester, pos)
            else:
                self.queues.pop(requester)
        return user_queue

    def remove_user_track(self, requester: int, pos: int) -> Optional[T]:
        user_queue = self.queues.get(requester)
        if user_queue is not None:
            if pos < len(user_queue):
                glob_pos = self._loc_to_glob(requester, pos)
                if glob_pos <= self.loop_offset:
                    self.loop_offset -= 1
                track = user_queue.pop(pos)
                self._clear_empty()
                return track

    def remove_track(self, track: T) -> Optional[Tuple[int, T]]:
        """
        Removes a track by identity
        """
        for queue in self.queues.values():
            for i, t in enumerate(queue):
                if t is track:
                    global_pos = self._loc_to_glob(t.requester, i)
                    removed = queue.pop(i)
                    self._clear_empty()
                    return global_pos, removed
        return None

    def remove_global_track(self, pos: int) -> Optional[T]:
        # Get the actual index of the song
        index = list(self).index(self.get_queue()[pos])

        if index <= self.loop_offset:
            self.loop_offset -= 1

        q, index = self._glob_to_loc(index)
        if q is None or index is None:
            return
        if queue := self.queues.get(q):
            track = queue.pop(index)
            self._clear_empty()
            return track

    def move_user_track(self, requester: int, initial: int, final: int) -> None:
        queue = self.queues.get(requester, [])
        if queue:
            try:
                track = queue.pop(initial)
                queue.insert(final, track)
                return track
            except IndexError:
                self.logger.debug(f"Got invalid index when moving track from {initial} to {final}")
                pass

    def shuffle_user_queue(self, requester: int) -> None:
        queue = self.queues.get(requester, [])
        if queue:
            shuffle(queue)

    def enable_looping(self, looping: bool) -> None:
        if (not self.looping) and looping:  # Enable only if not already enabled
            self.looping = looping
            self.loop_offset = 0
            self.logger.debug("Looping enabled")
        elif self.looping and not looping:  # Disable only if enabled
            # Copy queue in current (looping) state
            queue_copy = [track for track in self.get_queue()]
            self.queues = OrderedDict()
            self.looping = looping
            for track in queue_copy:
                self.add_track(track.requester, track)
            self.loop_offset = 0
            self.logger.debug("Looping disabled, queue reordered")

    # Switches the order of user queues
    def _shift_queues(self) -> None:
        if idx := self.first_queue:
            self.queues.move_to_end(idx)

    # Removes empty user queues
    def _clear_empty(self) -> None:
        to_remove = [q for q in reversed(self.queues) if not self.queues[q]]
        for i in to_remove:
            self.queues.pop(i)

    def _loc_to_glob(self, requester, pos) -> int:
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

    def _glob_to_loc(self, pos: int) -> Tuple[Optional[int], Optional[int]]:
        try:
            song: T = next(islice(self, pos, pos + 1))
        except (ValueError, StopIteration):
            return None, None
        user_queue = self.queues.get(song.requester, [])

        # In case song is in the priority queue
        if not user_queue or song not in user_queue:
            return None, pos

        for i, s in enumerate(user_queue):
            if s == song:
                return song.requester, i
        return None, None

    @property
    def first_queue(self) -> Optional[int]:
        try:
            return list(self.queues.keys())[0]
        except IndexError:
            pass

    @property
    def empty(self) -> bool:
        return len(self) == 0

    @property
    def history(self) -> QueueType:
        return list(reversed(self._history))
