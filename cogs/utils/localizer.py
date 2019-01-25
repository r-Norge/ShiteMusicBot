from glob import glob
from os import path

import re

from cogs.utils.dict_utils import flatten, SafeDict

import json



"""
Localizer for bot
"""

kmatch = re.compile('({[^{}]+})')

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

        tmp_d = flatten(self.localization_table)
        print(tmp_d)
        for lang, d in self.localization_table.items():
            self.localization_table[lang] = Localizer._parse_localization_dictionary(self.localization_table[lang], tmp_d)

    # internal function for loading a localization
    def _load_localization(self, lang):
        localization = self.localization_table.get(lang)
        if localization is None:
            raise Exception(f'Localization for {lang} does not exist')
        elif localization is False:
            print(f'Loading {lang}')
            self.localization_table[lang] = {}
            l_table = self.localization_table[lang]
            for file in glob(path.join(self.localization_folder, lang, "*.json")):
                file_base = path.basename(file).split(".")[0]
                print(f'{file_base} -> {file}')
                with open(file) as f:
                    data = json.load(f)
                
                l_table[file_base] = data
            
            l_table = flatten(l_table)
            self.localization_table[lang] = Localizer._parse_localization_dictionary(l_table, l_table)
            for file in glob(path.join(self.localization_folder, lang, "*.txt")):
                file_base = path.basename(file).split(".")[0]
                print(f'{file_base} -> {file}')
                with open(file) as f:
                    content = Localizer._parse_localization_string(f.read(), self.localization_table[lang])
                self.localization_table[lang][file_base] = content

    # parses and interpolates translation dictionary
    @staticmethod
    def _parse_localization_dictionary(d, lookup):
        n_dict = {}
        for k, v in d.items():
            if type(v) is str:
                n_dict[k] = Localizer._parse_localization_string(v, lookup)
            else:
                n_dict[k] = v
        return n_dict

    # parses and interpolates strings
    @staticmethod
    def _parse_localization_string(value, d):
        d = SafeDict(d)
        for match in kmatch.findall(value):
            nstr = match.replace(".", "/")
            value = value.replace(match, nstr)
        return value.format_map(d)
    
    # returns true if localization is currently loaded
    def isLoaded(self, lang):
        return self.localization_table.get(lang, False)
    
    # returns translation string from a key
    def get(self, key, lang=None):
        lang = lang or self.default_lang
        if not self.isLoaded(lang):
            self._load_localization(lang)
        
        return self.localization_table.get(lang, {}).get(key.replace(".", "/"))
        
        