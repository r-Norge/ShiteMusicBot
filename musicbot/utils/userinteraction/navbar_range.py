
class NavBarRange:
    def __init__(self, num_items: int, current_item: int, max_iter_length: int, add_ends: bool = True):
        self._num_items = num_items
        self._current_item = current_item
        self._max_iter_length = max_iter_length
        self._add_ends = add_ends

        # Start can not be before 0
        start = max(0, self._current_item - self._max_iter_length // 2)
        # Start can not be closer to end than max_iter_length
        self._start = min(start, self._num_items - self._max_iter_length)
        self._end = self._start + self._max_iter_length

    def __iter__(self):
        if (self._max_iter_length > self._num_items):
            return iter(range(0, self._num_items))

        mid_select_items = list(range(self._start, self._end))
        if self._add_ends:
            mid_select_items[0] = 0
            mid_select_items[-1] = self._num_items - 1
        return iter(mid_select_items)

    @property
    def end(self):
        return self._end

    @property
    def start(self):
        return self._end
