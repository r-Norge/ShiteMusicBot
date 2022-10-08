from .dictmapper import DictMapper


class TestDictMapper():
    def test_dict_mapper_basic_set(self):
        d = {}
        DictMapper.set(d, ["a", "b", "c"], 1)
        assert d == {"a": {"b": {"c": 1}}}

    def test_dict_mapper_basic_get(self):
        d = {"a": {"b": {"c": 1}}}
        assert DictMapper.get(d, ["a", "b", "c"]) == 1

    def test_get_variations(self):
        d = {"a": {"b": {"c": 1}}}

        assert DictMapper.get(d, ["a", "b", "c"]) == DictMapper.get(d["a"], ["b", "c"])
        assert DictMapper.get(d, ["a", "b", "c"]) == DictMapper.get(d["a"]["b"], ["c"])
        assert DictMapper.get(d, ["a", "b", "c"]) == d["a"]["b"]["c"]

    def test_get_sub_dictionaries(self):
        d = {"a": {"b": {"c": 1}}}
        assert DictMapper.get(d, ["a", "b"]) == d["a"]["b"]
        assert DictMapper.get(d["a"], ["b"]) == DictMapper.get(d["a"], ["b"])

    def test_set_variation(self):
        d = {"a": {"b": {"c": 1}}}
        d1 = {}
        d2 = {}

        DictMapper.set(d1, ["a", "b"], {"c": 1})
        assert d1 == d

        DictMapper.set(d2, ["a"], {"b": {"c": 1}})
        assert d2 == d

    def test_multiple_paths(self):
        d = {}

        DictMapper.set(d, ["a", "b1", "c"], 1)
        DictMapper.set(d, ["a", "b1", "d"], 2)
        DictMapper.set(d, ["a", "b2", "c"], 3)
        DictMapper.set(d, ["a", "b2", "d"], 4)

        expected = {
                "a": {
                    "b1": {
                        "c": 1,
                        "d": 2,
                       },
                    "b2": {
                        "c": 3,
                        "d": 4,
                       }
                   }
               }
        assert d == expected

    def test_overwrite(self):
        d = {}

        DictMapper.set(d, ["a", "b1", "c"], 1)
        DictMapper.set(d, ["a", "b1", "d"], 2)
        DictMapper.set(d, ["a", "b2", "c"], 3)
        DictMapper.set(d, ["a", "b2", "d"], 4)

        expected = {
                "a": {
                    "b1": {
                        "c": 1,
                        "d": 2,
                       },
                    "b2": {
                        "c": 3,
                        "d": 4,
                       }
                   }
               }
        assert d == expected

        DictMapper.set(d, ["a", "b2"], 4)
        expected = {
                "a": {
                    "b1": {
                        "c": 1,
                        "d": 2,
                       },
                    "b2": 4,
                   }
               }
        assert d == expected
