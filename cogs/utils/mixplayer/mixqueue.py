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

    # if pos is true also returns global positions of songs
    def get_user_queue(self, requester: int, pos: bool=False):
        queue = self.queues.get(requester, [])
        if pos and queue:
            pos = [self._loc_to_glob(requester, i) for i in range(len(queue))]
            combined = zip(queue, pos)
            return list(combined)
        return queue

    def pop_first(self):
        if self.priority_queue:
            next_song = self.priority_queue.pop(0)
            return next_song
        try:
            next_song = self.queues[self.first_queue].pop(0)
            self._shuffle()
            self._clear_empty()
            return next_song
        except KeyError:
            pass

    def add_song(self, requester: int, track: AudioTrack, pos: int=None):
        user_queue = self.queues.get(requester)
        if user_queue is None:
            self.queues[requester] = [track]
        elif pos is None:
            user_queue.append(track)
        else:
            user_queue.insert(pos, track)

    def add_next_song(self, track: AudioTrack):
        self.priority_queue.append(track)

    def remove_song_from(self, requester: int, pos: int):
        user_queue = self.queues.get(requester)
        if user_queue is not None:
            if pos < len(user_queue):
                user_queue.pop(pos)
                self._clear_empty()

    def remove_song_at(self, pos: int):
        q, pos = self._glob_to_loc(pos)
        if q is None or pos is None:
            return
        queue = self.queues.get(q)
        queue.pop(pos)
        self._clear_empty()

    def switch_user_songs(self, requester: int, first: int, second: int):
        queue = self.queues.get(requester, [])
        if queue:
            try:
                queue[first], queue[second] = queue[second], queue[first]
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
                song = queue[pos]
                for i, s in enumerate(self):
                    if s == song:
                        return i
            except IndexError:
                pass

    def _glob_to_loc(self, pos: int):
        song = None
        for i, s in enumerate(self):
            if i == pos:
                song = s
        if song is None:
            return None, None
        for requester, q in self.queues.items():
            for i, s in enumerate(q):
                if s == song:
                    return requester, i

    @property
    def first_queue(self):
        try:
            return list(self.queues.keys())[0]
        except IndexError:
            pass