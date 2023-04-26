import discord

from .basepaginator import BasePaginator


class TextPaginator(BasePaginator):
    def __init__(self, max_size=2000, max_lines=10, **embed_base):
        super().__init__(max_size=max_size, max_units=max_lines)
        self._current_page = []
        self.embed_base = embed_base

    def close_page(self):
        if self._current_page_size > 0:
            embed = discord.Embed(**self.embed_base)
            embed.description = '\n'.join(self._current_page)
            self._pages.append(embed)

            self._current_page_size = 0
            self._current_units = 0
            self._current_page = []

    def add_line(self, line='', *, empty=False):
        if len(line) > self._max_size:
            raise RuntimeError(f'Line exceeds maximum page size {self._max_size}')

        if self._current_page_size + len(line) + 1 > self._max_size:
            self.close_page()

        if self._current_units >= self._max_units:
            self.close_page()

        self._current_page_size += len(line) + 1
        self._current_units += 1
        self._current_page.append(line)

        if empty:
            self._current_page.append('')
            self._current_page_size += 1
