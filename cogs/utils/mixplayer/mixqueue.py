from collections import OrderedDict
from itertools import cycle, islice, chain
from random import shuffle
from lavalink import AudioTrack

def roundrobin(*iterables):
    "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
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

    def __str__(self):
        tmp = ''
        for requester in self.queues.keys():
            user_queue = list(map(str, self.queues[requester]))
            tmp += f'{requester}: {user_queue}\n'
        return tmp

    def __bool__(self):
        return not self.is_empty()

    def __iter__(self):
        global_queue = roundrobin(*[x for x in self.queues.values()])
        priority_queue = self.priority_queue 
        out = chain(priority_queue, global_queue)
        return out

    def __len__(self):
        length = 0
        for i in self:
            length += 1
        return length

    def get_queue(self):
        return list(self)

    def is_empty(self):
        return len(self) == 0

    def clear(self):
        self.queues = OrderedDict()
        self.priority_queue = []

    # if dual is true also returns global positions of tracks
    def get_user_queue(self, requester: int, dual: bool=False):
        queue = self.queues.get(requester, [])
        if dual and queue:
            pos = [self._loc_to_glob(requester, i) for i in range(len(queue))]
            combined = zip(queue, pos)
            return list(combined)
        return queue

    def pop_first(self):
        if self.priority_queue:
            next_track = self.priority_queue.pop(0)
            return next_track
        try:
            next_track = self.queues[self.first_queue].pop(0)
            self._shuffle()
            self._clear_empty()
            return next_track
        except KeyError:
            pass

    def add_track(self, requester: int, track: AudioTrack, pos: int=None):
        user_queue = self.queues.get(requester)
        if user_queue is None:
            self.queues[requester] = [track]
        elif pos is None:
            user_queue.append(track)
        else:
            user_queue.insert(pos, track)

    def add_next_track(self, track: AudioTrack):
        self.priority_queue.append(track)

    def remove_user_track(self, requester: int, pos: int):
        user_queue = self.queues.get(requester)
        if user_queue is not None:
            if pos < len(user_queue):
                user_queue.pop(pos)
                self._clear_empty()

    def remove_global_track(self, pos: int):
        q, pos = self._glob_to_loc(pos)
        if q is None or pos is None:
            return
        queue = self.queues.get(q)
        queue.pop(pos)
        self._clear_empty()

    def move_user_track(self, requester: int, initial: int, final: int):
        queue = self.queues.get(requester, [])
        if queue:
            try:
                track = queue.pop(initial)
                queue.insert(final, track)
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

    # Convert between global and local queue positions
    def _loc_to_glob(self, requester: int, pos: int):
        queue = self.queues.get(requester, [])
        if queue:
            try:
                track = queue[pos]
                for i, t in enumerate(self):
                    if t == track:
                        return i
            except IndexError:
                pass

    def _glob_to_loc(self, pos: int):
        track = None
        for i, t in enumerate(self):
            if i == pos:
                track = t
        if track is None:
            return None, None
        for requester, q in self.queues.items():
            for i, t in enumerate(q):
                if t == track:
                    return requester, i

    @property
    def first_queue(self):
        try:
            return list(self.queues.keys())[0]
        except IndexError:
            pass
