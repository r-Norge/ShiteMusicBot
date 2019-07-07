import os
import codecs
import locale as localee
import yaml


class Settings:
    def __init__(self, datadir, **default_settings):
        self._DATA_PATH = f"{datadir}/bot/"
        self._SETTINGS_PATH = self._DATA_PATH + 'settings.yaml'

        self.default_prefix = default_settings["prefix"]
        self.default_mod = default_settings["moderator role"]
        self.default_locale = default_settings["locale"]
        self.default_threshold = default_settings["threshold"]
        self.default_is_dynamic = default_settings["dynamic max duration"]

        if not self.default_locale:
            locale, codepage = localee.getlocale()
            default_locale, default_codepage = locale.getdefaultlocale()
            self.default_locale = locale or default_locale

        if not os.path.exists(self._DATA_PATH):
            os.makedirs(self._DATA_PATH)

        if not os.path.isfile(self._SETTINGS_PATH):
            with codecs.open(self._SETTINGS_PATH, "w+", encoding='utf8') as f:
                yaml.dump({}, f, indent=2)

        with codecs.open(self._SETTINGS_PATH, "r", encoding='utf8') as f:
            self.settings = yaml.load(f, Loader=yaml.SafeLoader)

    def _set(self, d, keys, val):
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

    def set(self, guild, setting, value):
        """ Set value in settings, will overwrite any existing values. """
        guild_id = str(guild.id)

        if guild_id not in self.settings.keys():
            self.settings[guild_id] = {}

        self.settings[guild_id]["_servername"] = guild.name
        self._set(self.settings[guild_id], setting.split('.'), value)

        with codecs.open(self._SETTINGS_PATH, 'w', encoding='utf8') as f:
            yaml.dump(self.settings, f, indent=2)

    def get(self, guild, setting, default=''):
        """ Gets a value from the settings if a default return value is specified
        it will return the default if no setting is found. If that default is a
        class attribute the value of the attribute will get returned."""
        guild_id = str(guild.id)

        if default and isinstance(default, str) and hasattr(self, default):
            default = getattr(self, default)
        elif not default:
            default = None

        if guild_id not in self.settings.keys():
            return default

        value = self._get(self.settings[guild_id], setting.split('.'))
        if value is not None:
            return value
        else:
            return default
