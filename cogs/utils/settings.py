import os
import json
import codecs
import locale


class Settings:
    def __init__(self, **default_settings):
        self._DATA_PATH = 'data/bot/'
        self._SETTINGS_PATH = self._DATA_PATH + 'settings.json'

        self.default_prefix = default_settings["prefix"]
        self.default_mod = default_settings["moderator_role"]
        self.default_locale = default_settings["locale"]
        self.default_threshold = default_settings["threshold"]

        if not self.default_locale:
            locale, codepage = locale.getlocale()
            default_locale, default_codepage = locale.getdefaultlocale()
            self.default_locale = locale or default_locale

        if not os.path.exists(self._DATA_PATH):
            os.makedirs(self._DATA_PATH)

        if not os.path.isfile(self._SETTINGS_PATH):
            with codecs.open(self._SETTINGS_PATH, "w+", encoding='utf8') as f:
                json.dump({}, f, indent=4)

        with codecs.open(self._SETTINGS_PATH, "r", encoding='utf8') as f:
            self.settings = json.load(f)

    def _set(self, d, keys, val):
        key = keys[0]
        if len(keys) == 1:
            if val is None:
                try:
                    d.pop(key)
                except:
                    pass
            else:
                d[key] = val
            return
        if key in d.keys():
            if not isinstance(d[key], dict):
                d[key] = {}
            self._set(d[key], keys[1:], val)
        else:
            d[key] = {}
            self._set(d[key], keys[1:], val)

    def _get(self, d, keys):
        key = keys[0]
        try:
            if len(keys) > 1 and isinstance(d[key], dict):
                return self._get(d[key], keys[1:])
            else:
                return d[key]
        except KeyError:
            return None

    def set(self, guild_id, setting, value):
        """ Set value in settings, will overwrite any existing values. """
        guild_id = str(guild_id)

        if guild_id not in self.settings.keys():
            self.settings[guild_id] = {}

        self._set(self.settings[guild_id], setting.split('.'), value)

        with codecs.open(self._SETTINGS_PATH, 'w', encoding='utf8') as f:
            json.dump(self.settings, f, indent=2)

    def get(self, guild_id, setting, default=''):
        """ Gets a value from the settings if a default return value is specified
        it will return the default if no setting is found. If that default is a
        class attribute the value of the attribute will get returned."""
        guild_id = str(guild_id)

        if default and isinstance(default, str) and hasattr(self, default):
            default = getattr(self, default)
        elif not default:
            default = None

        if guild_id not in self.settings.keys():
            return default

        value = self._get(self.settings[guild_id], setting.split('.'))
        if value:
            return value
        else:
            return default
