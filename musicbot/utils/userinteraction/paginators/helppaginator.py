import discord

from .fieldpaginator import FieldPaginator


class HelpPaginator(FieldPaginator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def force_close_page(self):
        self._pages.append(self._current_page)
        self._current_page_size = 0
        self._current_units = 0
        self._current_page = discord.Embed(**self._embed_base)

    def add_command_field(self, cmd_dict):
        if not isinstance(cmd_dict, dict):
            return
        aliases = cmd_dict.get('aliases', [])
        args = cmd_dict.get('args', '')
        description = cmd_dict.get('description', '')

        cmd = str(aliases[0])

        cmd += ' ' + args
        self.add_field(name=cmd, value=description, inline=False)
