# Discord Packages
from discord.ext import commands

from glob import glob
from os import path

import yaml

"""
Not the prettiest this, works by replacing any found aliases in a command string with the actual command names.
Allows per guild aliases of subcommands without doing anything to discord.py itself. Suggestions of better/correct
ways of doing this appreciated.
"""


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
            with open(path.join(self.localization_folder, lang, "commands.yaml"), "r", encoding='utf-8') as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
            self.localization_table[lang] = {'aliases': data, 'commands': self._gen_alias_dict(data)}

    def convert_alias(self, locale, default=None, parents=None):
        if parents is None:
            parents = []
        try:
            locale = self.localization_table[locale]
        except KeyError:
            locale = self.localization_table[self.default_lang]

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

    def get_cmd_help(self, locale, command=None, parents=None):
        """ Fetches the command info dictionary """
        if parents is None:
            parents = []
        locale = self.localization_table[locale]

        def traverse(command_tree, parents, command):
            # Return the command when no more parents exist
            if not parents:
                return command_tree.get(command, [])

            parent = command_tree.get(parents.pop(0), None)
            if not parent:
                return None
            command_tree = parent.get('sub_commands', [])
            if not command_tree:
                return None
            return traverse(command_tree, parents, command)

        command_tree = locale['aliases']
        if command:
            return traverse(command_tree, parents, command)
        return command_tree

    def get_command(self, ctx):
        """ Get a top level command. """
        if not ctx.prefix:
            ctx.command = None
            return ctx
        ctx.view.undo()
        ctx.invoker = ctx.view.buffer[ctx.view.index:ctx.view.end]
        alias = ctx.view.get_word()
        command = self.convert_alias(ctx.locale, alias)
        ctx.invoked_with = command
        ctx.command = ctx.bot.all_commands.get(command)
        if ctx.command and isinstance(ctx.command, commands.GroupMixin):
            ctx = self.get_subcommand(ctx, ctx.command, [str(ctx.command)])
        return ctx

    def _replace_command(self, view, index, alias, command):
        buf = view.buffer
        changed = buf[index:]
        view.buffer = buf[:index] + changed.replace(alias, command, 1)
        return view

    def get_subcommand(self, ctx, group=None, parents=None):
        """ Recursicely replaces all subcommand aliases with subcommands."""
        if parents is None:
            parents = []
        view = ctx.view
        prev = view.previous
        idx = view.index

        # get the alias used
        view.skip_ws()
        alias = view.get_word()

        sub_command = self.convert_alias(ctx.locale, alias, parents.copy())
        parents.append(sub_command)

        # Replace the alias in the command
        self._replace_command(view, idx, alias, sub_command)

        # Update the view to account for difference in length
        strdiff = len(sub_command) - len(alias)
        view.end += strdiff
        view.index += strdiff

        # Get the subcommand
        if group:
            sub = group.all_commands.get(sub_command, None)
        else:
            sub = ctx.bot.all_commands.get(sub_command, None)

        # Translate any subsubcommands
        if sub and isinstance(sub, commands.GroupMixin):
            self.get_subcommand(ctx, sub, parents)

        # Reset the view indexes
        view.index = idx
        view.previous = prev
        return ctx
