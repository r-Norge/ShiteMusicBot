import os
import json
import codecs


class Settings:
    def __init__(self, **default_settings):
        self.DATA_PATH = 'data/settings/'
        self.SETTINGS_PATH = self.DATA_PATH + 'settings.json'
        self.default_prefix = default_settings["default_prefix"]
        self.default_admin = default_settings["default_admin"]
        self.default_mod = default_settings["default_mod"]

        if not os.path.exists(self.DATA_PATH):
            os.makedirs(self.DATA_PATH)

        if not os.path.isfile(self.SETTINGS_PATH):
            with codecs.open(self.SETTINGS_PATH, "w+", encoding='utf8') as f:
                json.dump({"prefixes": {},
                           "roles": {}}, f, indent=4)

        with codecs.open(self.SETTINGS_PATH, "r", encoding='utf8') as f:
            self.settings = json.load(f)

    def get_prefix(self, guild_id):
        guild_id = str(guild_id)
        if guild_id in self.settings["prefixes"].keys():
            return self.settings["prefixes"][guild_id]
        return self.default_prefix

    def set_prefix(self, guild_id, prefixes):
        if prefixes is None:
            self.settings["prefixes"].pop(str(guild_id), None)
        else:
            self.settings["prefixes"][str(guild_id)] = prefixes
        with codecs.open(self.SETTINGS_PATH, "w", encoding='utf8') as f:
            json.dump(self.settings, f, indent=4)

    def get_mod_role(self, guild_id):
        guild_id = str(guild_id)
        if guild_id in self.settings["roles"].keys():
            if 'mod' in self.settings["roles"][guild_id].keys():
                return self.settings["roles"][guild_id]['mod']
        return self.default_mod

    def get_admin_role(self, guild_id):
        guild_id = str(guild_id)
        if guild_id in self.settings["roles"].keys():
            if 'admin' in self.settings["roles"][guild_id].keys():
                return self.settings["roles"][guild_id]['admin']
        return self.default_admin

    def set_mod_admin_role(self, guild_id, admin, mod):
        guild_id = str(guild_id)
        if admin is None or mod is None:
            self.settings["role"].pop(guild_id, None)
        else:
            self.settings["role"][guild_id]["mod"] = mod
            self.settings["role"][guild_id]["admin"] = admin

        with codecs.open(self.SETTINGS_PATH, "w", encoding='utf8') as f:
            json.dump(self.settings, f, indent=4)
