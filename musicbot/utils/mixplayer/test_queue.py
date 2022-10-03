from .mixqueue import MixQueue


class TrackMock:
    def __init__(self, requester, title):
        self.requester = requester
        self.title = str(requester)+title

    def __eq__(self, other):
        return self.title == other.title

    def __str__(self):
        return f"({self.requester}: {self.title})"

    def __repr__(self):
        return str(self)


class TestMixQueue():
    def list_to_requests(self, list_of_str):
        tracks = []
        for item in list_of_str:
            requester = int(item[0])
            title = str(item[1:])
            tracks.append(TrackMock(requester, title))
        return tracks

    def setup_baisc_queue(self):
        queue = MixQueue()
        queue.add_track(2, TrackMock(2, "a"))
        queue.add_track(2, TrackMock(2, "b"))

        queue.add_track(1, TrackMock(1, "a"))
        queue.add_track(1, TrackMock(1, "b"))
        queue.add_track(1, TrackMock(1, "c"))
        queue.add_track(1, TrackMock(1, "d"))

        queue.add_track(3, TrackMock(3, "a"))
        queue.add_track(3, TrackMock(3, "b"))
        return queue

    def test_queue_mixing_double(self):
        queue = MixQueue()
        requester1 = 1
        requester2 = 2
        queue.add_track(requester1, TrackMock(1, "a"))
        queue.add_track(requester1, TrackMock(1, "b"))
        queue.add_track(requester1, TrackMock(1, "c"))
        queue.add_track(requester1, TrackMock(1, "d"))
        queue.add_track(requester1, TrackMock(1, "e"))

        queue.add_track(requester2, TrackMock(2, "a"))
        queue.add_track(requester2, TrackMock(2, "b"))
        queue.add_track(requester2, TrackMock(2, "c"))

        assert list(queue) == self.list_to_requests(["1a", "2a", "1b", "2b", "1c", "2c", "1d", "1e"])

    def test_queue_mixing_triple(self):
        queue = self.setup_baisc_queue()
        assert list(queue) == self.list_to_requests(["2a", "1a", "3a", "2b", "1b", "3b", "1c", "1d"])

    def test_priority_queue(self):
        queue = self.setup_baisc_queue()

        queue.add_next_track("priority_item1")
        queue.add_next_track("priority_item2")

        assert queue.pop_first() == "priority_item1"
        assert queue.pop_first() == "priority_item2"
        assert queue.pop_first() == TrackMock(2, "a")
        assert queue.pop_first() == TrackMock(1, "a")

    def test_user_queue(self):
        queue = self.setup_baisc_queue()
        assert queue.get_user_queue(1) == [TrackMock(1, "a"), TrackMock(1, "b"), TrackMock(1, "c"), TrackMock(1, "d")]
        assert queue.get_user_queue(2) == [TrackMock(2, "a"), TrackMock(2, "b")]
        assert queue.get_user_queue(3) == [TrackMock(3, "a"), TrackMock(3, "b")]

    def test_user_queue_with_index(self):
        queue = self.setup_baisc_queue()
        assert queue.get_user_queue_with_index(1) == [(TrackMock(1, "a"), 1), (TrackMock(1, "b"), 4),
                                                      (TrackMock(1, "c"), 6), (TrackMock(1, "d"), 7)]
        assert queue.get_user_queue_with_index(2) == [(TrackMock(2, "a"), 0), (TrackMock(2, "b"), 3)]
        assert queue.get_user_queue_with_index(3) == [(TrackMock(3, "a"), 2), (TrackMock(3, "b"), 5)]

    def test_looping_behavior(self):
        queue = self.setup_baisc_queue()

        # Before looping
        assert queue.get_user_queue_with_index(1) == [(TrackMock(1, "a"), 1), (TrackMock(1, "b"), 4),
                                                      (TrackMock(1, "c"), 6), (TrackMock(1, "d"), 7)]
        assert queue.get_user_queue_with_index(2) == [(TrackMock(2, "a"), 0), (TrackMock(2, "b"), 3)]
        assert queue.get_user_queue_with_index(3) == [(TrackMock(3, "a"), 2), (TrackMock(3, "b"), 5)]
        assert list(queue) == self.list_to_requests(["2a", "1a", "3a", "2b", "1b", "3b", "1c", "1d"])

        queue.enable_looping(True)
        assert queue.pop_first() == TrackMock(2, "a")
        assert list(queue) == self.list_to_requests(["2a", "1a", "3a", "2b", "1b", "3b", "1c", "1d"])
        assert queue.get_user_queue_with_index(1) == [(TrackMock(1, "a"), 2), (TrackMock(1, "b"), 5),
                                                      (TrackMock(1, "c"), 7), (TrackMock(1, "d"), 0)]
        assert queue.get_user_queue_with_index(2) == [(TrackMock(2, "a"), 1), (TrackMock(2, "b"), 4)]
        assert queue.get_user_queue_with_index(3) == [(TrackMock(3, "a"), 3), (TrackMock(3, "b"), 6)]

        popped_queue_before_loop_point = self.list_to_requests(["1a", "3a", "2b", "1b", "3b", "1c", "1d"])
        for item in popped_queue_before_loop_point:
            assert item == queue.pop_first()

        popped_queue_after_loop_point = self.list_to_requests(["2a", "1a", "3a", "2b", "1b", "3b", "1c", "1d"])
        for item in popped_queue_after_loop_point:
            assert item == queue.pop_first()

        popped_queue_after_loop_point = self.list_to_requests(["2a", "1a", "3a", "2b"])
        for item in popped_queue_after_loop_point:
            assert item == queue.pop_first()

        queue.enable_looping(False)
        # When the queue is disabled we take the current requester order of
        # the looped queue and regenerate the mixed queue from that
        popped_queue_after_loop_disabled = self.list_to_requests(["1b", "3b", "2a", "1c", "3a", "2b", "1d", "1a"])
        for item in popped_queue_after_loop_disabled:
            assert item == queue.pop_first()

        assert list(queue) == []
