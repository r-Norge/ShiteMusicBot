import yaml
from glob import glob
from os import path

class Aliaser:
    def __init__(self, localization_folder, default_lang):
        self.localization_folder = path.realpath(localization_folder)
        self.default_lang = default_lang
        self.index_localizations()
        self.load_localizations()

    def _invert(self, d):
        inverted = {}
        for command in d:
            for alias in d[command]:
                inverted[alias] = command
        return inverted

    def index_localizations(self):
        self.localization_table = {}
        for folder in glob(path.join(self.localization_folder, "*/")):
            if 'global' in folder:
                continue
            folder_base = path.basename(path.dirname(folder))
            self.localization_table[folder_base] = False

    def load_localizations(self):
        for lang in self.localization_table.keys():
            with open(path.join(self.localization_folder, lang, "aliases.yaml"), "r", encoding='utf-8') as f:
                data = yaml.load(f)
            self.localization_table[lang] = {'aliases': data, 'commands': self._invert(data)}

    def get_command(self, locale, alias):
        locale = self.localization_table[locale]
        return locale['commands'].get(alias, None)

    def get_alias(self, locale, command):
        locale = self.localization_table[locale]
        return locale['aliases'].get(command, [])