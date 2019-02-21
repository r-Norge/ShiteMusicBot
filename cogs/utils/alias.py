import discord
import yaml

from glob import glob
from os import path

from discord.ext import commands

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

    def cmd_from_alias(self, locale, alias, default=None):
        locale = self.localization_table[locale]
        return locale['commands'].get(alias, default)

    def get_alias(self, locale, command):
        locale = self.localization_table[locale]
        return locale['aliases'].get(command, [])

    def get_command(self, ctx):
        ctx.view.undo()
        alias = ctx.view.get_word()
        command = self.cmd_from_alias(ctx.locale, alias, alias)
        ctx.invoked_with = command
        ctx.command = ctx.bot.all_commands.get(command)
        return ctx

    def subcommand_from_alias(self, ctx, group):
        """ Recursicely replaces all subcommand aliases with subcommands."""
        view = ctx.view
        prev = view.previous
        idx = view.index

        # get the alias used
        view.skip_ws()
        alias = view.get_word()
        subcmd = self.cmd_from_alias(ctx.locale, alias, alias)

        # Replace the alias in the command
        view.buffer = view.buffer.replace(alias, subcmd)

        # Update the view to account for difference in length
        strdiff = len(subcmd) - len(alias)
        view.end += strdiff
        view.index += strdiff

        # Get the subcommand
        sub = group.all_commands.get(subcmd, None)

        # Translate any subsubcommands 
        if sub and isinstance(sub, commands.GroupMixin):
            self.subcommand_from_alias(ctx, sub)

        # Reset the view indexes 
        view.index = idx
        view.previous = prev
        return ctx