# Discord Packages
from lavalink import AudioTrack

from collections import OrderedDict, deque
from itertools import chain, cycle, islice
from random import shuffle


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
        self.looping = False
        self.loop_offset = 0

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
        if self.looping:
            offset = self.loop_offset
            return list(self)[offset:] + list(self)[:offset]
        else:
            return list(self)

    def clear(self):
        self.queues = OrderedDict()
        self.priority_queue = []
        self.looping = False
        self.loop_offset = 0

    # if dual is true also returns global positions of tracks
    def get_user_queue(self, requester: int, dual: bool = False):
        queue = self.queues.get(requester, [])
        if dual and queue:
            pos = [self._loc_to_glob(requester, i) for i in range(len(queue))]
            if self.looping:
                pos = [(p + self.loop_offset) % len(self) for p in pos]
            combined = zip(queue, pos)
            return list(combined)
        return queue

    def pop_first(self):
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
                    print(e)
                    print(self.loop_offset)
                    print(len(self))
                    self.loop_offset = min(self.loop_offset, len(self)-1)
            else:
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
            if self.looping:
                # Should work, kinda hacky.
                for pos, track in reversed(list(enumerate(user_queue))):
                    self.remove_user_track(requester, pos)
            else:
                self.queues.pop(requester)

    def remove_user_track(self, requester: int, pos: int):
        user_queue = self.queues.get(requester)
        if user_queue is not None:
            if pos < len(user_queue):
                glob_pos = self._loc_to_glob(requester, pos)
                if glob_pos <= self.loop_offset:
                    self.loop_offset -= 1
                track = user_queue.pop(pos)
                self._clear_empty()
                return track

    def remove_global_track(self, pos: int):
        # Get the actual index of the song
        pos = list(self).index(self.get_queue()[pos])

        if pos <= self.loop_offset:
            self.loop_offset -= 1

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

    def enable_looping(self, looping):
        if (not self.looping) and looping:  # Not enabled and turning on
            self.looping = looping
            self.loop_offset = 0
        elif self.looping and not looping:  # Enabled to turning off
            tmp = [track for track in self.get_queue()]
            for key, _ in self.queues.items():
                self.queues = OrderedDict()
            self.looping = looping
            for track in tmp:
                self.add_track(track.requester, track)
            self.loop_offset = 0

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
