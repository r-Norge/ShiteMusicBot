
from .navbar_range import NavBarRange


class TestCenteredRange():
    def test_centered_basic_range(self):
        nav_range = NavBarRange(num_items=15, current_item=6, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [3, 4, 5, 6, 7, 8, 9]

    def test_centered_padded_range(self):
        nav_range = NavBarRange(num_items=15, current_item=6, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 4, 5, 6, 7, 8, 14]

    def test_beginning_basic_range(self):
        nav_range = NavBarRange(num_items=15, current_item=0, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [0, 1, 2, 3, 4, 5, 6]
        nav_range = NavBarRange(num_items=15, current_item=1, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [0, 1, 2, 3, 4, 5, 6]
        nav_range = NavBarRange(num_items=15, current_item=3, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [0, 1, 2, 3, 4, 5, 6]

        # Should be shifted
        nav_range = NavBarRange(num_items=15, current_item=4, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [1, 2, 3, 4, 5, 6, 7]

    def test_beginning_padded_range(self):
        nav_range = NavBarRange(num_items=15, current_item=0, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 1, 2, 3, 4, 5, 14]
        nav_range = NavBarRange(num_items=15, current_item=1, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 1, 2, 3, 4, 5, 14]
        nav_range = NavBarRange(num_items=15, current_item=3, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 1, 2, 3, 4, 5, 14]

        # Should be shifted
        nav_range = NavBarRange(num_items=15, current_item=4, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 2, 3, 4, 5, 6, 14]

    def test_end_basic_range(self):
        nav_range = NavBarRange(num_items=15, current_item=14, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [8, 9, 10, 11, 12, 13, 14]
        nav_range = NavBarRange(num_items=15, current_item=13, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [8, 9, 10, 11, 12, 13, 14]
        nav_range = NavBarRange(num_items=15, current_item=11, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [8, 9, 10, 11, 12, 13, 14]

        # Should be shifted
        nav_range = NavBarRange(num_items=15, current_item=10, max_iter_length=7, add_ends=False)
        assert list(nav_range) == [7, 8, 9, 10, 11, 12, 13]

    def test_end_padded_range(self):
        nav_range = NavBarRange(num_items=15, current_item=14, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 9, 10, 11, 12, 13, 14]
        nav_range = NavBarRange(num_items=15, current_item=13, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 9, 10, 11, 12, 13, 14]
        nav_range = NavBarRange(num_items=15, current_item=11, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 9, 10, 11, 12, 13, 14]

        # Should be shifted
        nav_range = NavBarRange(num_items=15, current_item=10, max_iter_length=7, add_ends=True)
        assert list(nav_range) == [0, 8, 9, 10, 11, 12, 14]

    def test_short_range(self):
        nav_range = NavBarRange(num_items=15, current_item=7, max_iter_length=25)
        assert list(nav_range) == list(range(15))
