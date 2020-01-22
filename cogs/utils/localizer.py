from glob import glob
from os import path

import re

from cogs.utils.dict_utils import flatten, SafeDict

import yaml

import copy
from discord import Embed

"""
Localizer for bot
"""

kmatch = re.compile('({(?!_)([^{}]+)})')


class Localizer:
    def __init__(self, localization_folder, default_lang):
        self.localization_folder = path.realpath(localization_folder)
        self.default_lang = default_lang
        # look for localization folders
        self.index_localizations()
        # load localizations
        self.load_localizations()

    # indexes localization folder
    def index_localizations(self):
        self.localization_table = {}
        for folder in glob(path.join(self.localization_folder, "*/")):
            folder_base = path.basename(path.dirname(folder))
            self.localization_table[folder_base] = False

    # loads all localizations
    def load_localizations(self):
        for lang in self.localization_table.keys():
            self.localization_table[lang] = False
            self._load_localization(lang)

        self.all_localizations = flatten(self.localization_table)
        for lang, d in self.localization_table.items():
            self.localization_table[lang] = Localizer._parse_localization_dictionary(self.localization_table[lang],
                                                                                     self.all_localizations)

    # internal function for loading a localization
    def _load_localization(self, lang):
        localization = self.localization_table.get(lang)
        if localization is None:
            raise Exception(f'Localization for {lang} does not exist')
        elif localization is False:
            self.localization_table[lang] = {}
            l_table = self.localization_table[lang]
            for file in glob(path.join(self.localization_folder, lang, "*.yaml")):
                if 'aliases' in file or 'commands' in file:
                    continue
                file_base = path.basename(file).split(".")[0]
                with open(file, "r", encoding='utf-8') as f:
                    data = yaml.load(f, Loader=yaml.SafeLoader)

                l_table[file_base] = data

            for file in glob(path.join(self.localization_folder, lang, "*.txt")):
                file_base = path.basename(file).split(".")[0]
                with open(file, "r", encoding='utf-8') as f:
                    content = f.read()
                l_table[file_base] = content

            l_table = flatten(l_table)
            # parsing a few times to resolve all values
            for i in range(0, 5):
                l_table = Localizer._parse_localization_dictionary(l_table, l_table)

            self.localization_table[lang] = Localizer._parse_localization_dictionary(l_table, l_table)

    # parses and interpolates translation dictionary
    @staticmethod
    def _parse_localization_dictionary(d, lookup, prefix=None):
        n_dict = {}
        for k, v in d.items():
            if type(v) is str:
                n_dict[k] = Localizer._parse_localization_string(v, lookup, prefix)
            else:
                n_dict[k] = v
        return n_dict

    @staticmethod
    def _replace_keys(value, prefix=None):
        for outer, inner in kmatch.findall(value):
            nstr = inner
            if prefix is not None:
                nstr = f'{prefix}.{inner}'
            nstr = f'{{{nstr}}}'
            nstr = nstr.replace(".", "/")
            value = value.replace(outer, nstr)
        return value
    # parses and interpolates strings
    @staticmethod
    def _parse_localization_string(value, d, prefix=None):
        d = SafeDict(d)
        value = Localizer._replace_keys(value, prefix)
        return value.format_map(d)

    # returns true if localization is currently loaded
    def isLoaded(self, lang):
        return self.localization_table.get(lang, False)

    def getAvaliableLocalizations(self):
        return self.localization_table.keys()

    # returns translation string from a key
    def get(self, key, lang=None):
        lang = lang if lang in self.localization_table.keys() else self.default_lang
        if not self.isLoaded(lang):
            self._load_localization(lang)

        return self.localization_table.get(lang, {}).get(key.replace(".", "/"))

    # inserts translations into a string
    def format_str(self, s, lang=None, prefix=None, **kvpairs):
        lang = lang if lang in self.localization_table.keys() else self.default_lang
        if not self.isLoaded(lang):
            self._load_localization(lang)

        ns = Localizer._parse_localization_string(s, self.localization_table.get(lang, {}), prefix)
        ns = Localizer._parse_localization_string(ns, self.all_localizations, prefix)
        return ns.format_map(SafeDict(kvpairs))

    # inserts translations into a values of a dictionary
    def format_dict(self, d, lang=None, prefix=None, **kvpairs):
        lang = lang if lang in self.localization_table.keys() else self.default_lang
        if not self.isLoaded(lang):
            self._load_localization(lang)

        nd = copy.deepcopy(d)
        cursorQueue = [nd]
        while cursorQueue:
            cursor = cursorQueue.pop()
            for k, v in (cursor.items() if type(cursor) == dict else enumerate(cursor)):
                if type(v) == str:
                    # insert translations based on lang
                    cursor[k] = self.format_str(v, lang, prefix, **kvpairs)
                elif type(v) == dict or type(v) == list:
                    cursorQueue.append(v)

        return nd

    # inserts translations into a values of a embed
    def format_embed(self, embed, lang=None, prefix=None, **kvpairs):
        raw = embed.to_dict()
        return Embed.from_dict(self.format_dict(raw, lang, prefix, **kvpairs))


class LocalizerWrapper:
    def __init__(self, localizer, lang=None, prefix=None):
        self.localizer = localizer
        self.lang = lang
        self.prefix = prefix

    def format_str(self, s, **kvpairs):
        return self.localizer.format_str(s, self.lang, self.prefix, **kvpairs)

    def format_dict(self, d, **kvpairs):
        return self.localizer.format_dict(d, self.lang, self.prefix, **kvpairs)

    def format_embed(self, embed, **kvpairs):
        return self.localizer.format_embed(embed, self.lang, self.prefix, **kvpairs)
