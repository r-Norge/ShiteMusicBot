# Discord Packages
import discord

import codecs
import locale as localee
import os

import yaml

from .dictmapper import DictMapper


class Settings():
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

    def set(self, identifier, setting, value):
        """ Set value in settings, will overwrite any existing values. """
        guild_name = None
        if isinstance(identifier, discord.Guild):
            guild_name = identifier.name
            identifier = str(identifier.id)

        if identifier not in self.settings.keys():
            self.settings[identifier] = {}

        if guild_name:
            self.settings[identifier]["_servername"] = guild_name
        DictMapper.set(self.settings[identifier], setting.split('.'), value)

        with codecs.open(self._SETTINGS_PATH, 'w', encoding='utf8') as f:
            yaml.dump(self.settings, f, indent=2)

    def get(self, identifier, setting, default=''):
        """ Gets a value from the settings if a default return value is specified
        it will return the default if no setting is found. If that default is an
        attribute of the settings class, the value of the attribute will get returned."""
        if isinstance(identifier, discord.Guild):
            identifier = str(identifier.id)

        if default and isinstance(default, str) and hasattr(self, default):
            default = getattr(self, default)
        elif default == '':
            default = None

        if identifier not in self.settings.keys():
            return default

        value = DictMapper.get(self.settings[identifier], setting.split('.'))
        if value is not None:
            return value
        else:
            return default
