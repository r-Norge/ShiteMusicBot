import discord

from .basepaginator import BasePaginator


class FieldPaginator(BasePaginator):
    def __init__(self, max_size=5000, max_fields=8, **embed_base):
        super().__init__(max_size=max_size, max_units=max_fields)
        self._embed_base = embed_base
        self._current_page = discord.Embed(**self._embed_base)

    def close_page(self):
        if self._current_page_size > 0:
            self._pages.append(self._current_page)
            self._current_page_size = 0
            self._current_units = 0
            self._current_page = discord.Embed(**self._embed_base)

    def add_field(self, name, value, inline=False):
        field = {"name": name, "value": value}
        fieldsize = sum([len(val) for _, val in field.items()])
        if len(name) > 256 or len(value) > 1024:
            raise RuntimeError('Maximum field size exceeded, max name length: 256. max value length: 1024.')

        if self._current_page_size + fieldsize > self._max_size:
            self.close_page()

        if self._current_units >= self._max_units:
            self.close_page()

        field["inline"] = inline
        self._current_page_size += fieldsize
        self._current_units += 1
        self._current_page.add_field(**field)
