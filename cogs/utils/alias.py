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

    def _gen_alias_dict(self, commands):
        """ Reverses the direction of a dict of commans→aliases to be alias→command. """
        inverted = {}
        subcommands = {}
        for cmd, properties in commands.items():
            if isinstance(properties, list):
                for alias in properties:
                    inverted[alias] = cmd
            else:
                for alias in properties['aliases']:
                    inverted[alias] = cmd
                if properties.get('sub_commands', None):
                    subcommands[cmd] = self._gen_alias_dict(properties['sub_commands'])
        inverted['sub_commands'] = subcommands
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
            self.localization_table[lang] = {'aliases': data, 'commands': self._gen_alias_dict(data)}

    def convert_alias(self, locale, alias, default=None, parents=[]):
        locale = self.localization_table[locale]

        # Traverse through the alias tree as dictated by the parents list
        def traverse(alias_tree, parents, alias):
            # Return the command when no more parents exist
            if not parents:
                return alias_tree.get(alias, None)
            parent = parents.pop(0)
            sub_commands = alias_tree.get('sub_commands', None)
            if not sub_commands:
                return None
            alias_tree = sub_commands.get(parent, None)
            if not alias_tree:
                return None
            return traverse(alias_tree, parents, alias)

        alias_tree = locale['commands']
        command = traverse(alias_tree, parents, default)
        if command:
            return command
        return default

    def get_alias(self, locale, command):
        locale = self.localization_table[locale]
        return locale['aliases'].get(command, [])

    def get_command(self, ctx):
        """ Get a top level command. """
        if not ctx.prefix:
            ctx.command = None
            return ctx
        ctx.view.undo()
        alias = ctx.view.get_word()
        command = self.convert_alias(ctx.locale, alias, alias)
        ctx.invoked_with = command
        ctx.command = ctx.bot.all_commands.get(command)
        return ctx

    def get_subcommand(self, ctx, group, parents=[]):
        """ Recursicely replaces all subcommand aliases with subcommands."""
        view = ctx.view
        prev = view.previous
        idx = view.index

        # get the alias used
        view.skip_ws()
        alias = view.get_word()

        subcmd = self.convert_alias(ctx.locale, alias, alias, parents.copy())
        parents.append(subcmd)

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
            self.get_subcommand(ctx, sub, parents)

        # Reset the view indexes 
        view.index = idx
        view.previous = prev
        return ctx