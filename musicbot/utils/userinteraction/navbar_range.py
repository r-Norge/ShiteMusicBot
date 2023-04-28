
class NavBarRange:
    def __init__(self, num_items: int, current_item: int, max_iter_length: int, add_ends: bool = True):
        self.num_items = num_items
        self.current_item = current_item
        self.max_iter_length = max_iter_length
        self.add_ends = add_ends

    def __iter__(self):
        if (self.max_iter_length > self.num_items):
            return iter(range(0, self.num_items))

        # Start can not be before 0
        start = max(0, self.current_item - self.max_iter_length // 2)
        # Start can not be closer to end than max_iter_length
        start = min(start, self.num_items - self.max_iter_length)
        end = start + self.max_iter_length

        mid_select_items = list(range(start, end))
        if self.add_ends:
            mid_select_items[0] = 0
            mid_select_items[-1] = self.num_items - 1
        return iter(mid_select_items)

    def _make_truncated_range(self, start, end):
        actual_start = max(start, 0)
        actual_end = min(self.max_iter_length, end)
        return range(actual_start, actual_end)
