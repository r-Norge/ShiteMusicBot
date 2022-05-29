
class DictMapper:
    """
        Base class for interacting with nested dictionaries through lists of keys
        E.g. mapping ["a", "b", "c"] to example_dictionary["a"]["b"]["c"]
    """

    @staticmethod
    def set(d, keys, val):
        key = keys[0]
        if len(keys) == 1:
            if val is None:
                try:
                    d.pop(key)
                except KeyError:
                    pass
            else:
                d[key] = val
            return
        if key in d.keys():
            if not isinstance(d[key], dict):
                d[key] = {}
            DictMapper.set(d[key], keys[1:], val)
        else:
            d[key] = {}
            DictMapper.set(d[key], keys[1:], val)

    @staticmethod
    def get(d, keys):
        key = keys[0]
        try:
            if len(keys) > 1 and isinstance(d[key], dict):
                return DictMapper.get(d[key], keys[1:])
            else:
                return d[key]
        except KeyError:
            return None
