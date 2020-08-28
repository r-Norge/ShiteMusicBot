# Discord Packages
import discord

import asyncio


class CantScroll(Exception):
    pass


class BasePaginator:
    def __init__(self, max_size=2000, max_units=10):
        self._pages = []
        self._current_page_size = 0
        self._current_units = 0
        self._max_size = max_size
        self._max_units = max_units

    def close_page(self):
        pass

    def add_page_indicator(self, localizer, localizer_str=None, **kvpairs):
        self.close_page()
        if localizer_str:
            for i, page in enumerate(self._pages, start=1):
                page.set_footer(text=localizer.format_str(localizer_str, _current=i,
                                                          _total=len(self._pages), **kvpairs))
        else:
            for i, page in enumerate(self._pages, start=1):
                page.set_footer(text=f"{i}/{len(self._pages)}")

    def append_paginator(self, paginator):
        if not isinstance(paginator, BasePaginator):
            raise TypeError('Paginator needs to be a subclass of BasePaginator.')
        self.close_page()
        for page in paginator.pages:
            self.pages.append(page)

    @property
    def pages(self):
        if self._current_page_size > 0:
            self.close_page()
        return self._pages


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


class QueuePaginator(TextPaginator):
    def __init__(self, localizer, queue, color, user_name: str = None):
        self.localizer = localizer
        self.queue = queue

        if user_name is None:
            title = localizer.format_str("{queue.length}", _length=len(queue))
        else:
            title = localizer.format_str("{queue.userqueue}",  _user=user_name, _length=len(queue))

        super().__init__(max_lines=10, **{"color": color, "title": title})

        for index, temp in enumerate(queue):
            if user_name is None:
                track = temp
                queued_track = localizer.format_str("{queue.globaltrack}", _index=index+1,  _title=track.title,
                                                    _uri=track.uri, _user_id=track.requester)
            else:
                track, globpos = temp
                queued_track = localizer.format_str("{queue.usertrack}", _index=index+1, _globalindex=globpos+1,
                                                    _title=track.title, _uri=track.uri)

            self.add_line(queued_track)
        self.add_page_indicator(self.localizer, "{queue.pageindicator}")


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


# Maybe slightly very copied from rdanny
# Thanks danny <3

class Scroller:
    def __init__(self, ctx, paginator, timeout=120.0, clear_on_timeout=False, clear_on_exit=True, clear_command=True):

        if not isinstance(paginator, BasePaginator):
            raise TypeError('Paginator needs to be a subclass of BasePaginator.')

        self.bot = ctx.bot
        self.pages = paginator.pages
        self.cmdmsg = ctx.message
        self.message = ctx.message
        self.channel = ctx.channel
        self.author = ctx.author

        self.timeout = timeout
        self.timeout_delete = clear_on_timeout
        self.exit_delete = clear_on_exit
        self.clear_command = clear_command

        if len(self.pages) > 1:
            self.scrolling = True
        else:
            self.scrolling = False
        self.reaction_emojis = [
            ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.first_page),
            ('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
            ('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
            ('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.last_page),
            ('❌', self.stop_scrolling),
        ]

        if ctx.guild is not None:
            self.permissions = self.channel.permissions_for(ctx.guild.me)
        else:
            self.permissions = self.channel.permissions_for(ctx.bot.user)

        if not self.permissions.embed_links:
            raise CantScroll('Bot does not have embed links permission.')

        if not self.permissions.send_messages:
            raise CantScroll('Bot cannot send messages.')

        if self.scrolling:
            # verify we can actually use the pagination session
            if not self.permissions.add_reactions:
                raise CantScroll('Bot does not have add reactions permission.')

            if not self.permissions.read_message_history:
                raise CantScroll('Bot does not have Read Message History permission.')

    async def send(self):
        self.current_page = 0
        # No embeds to scroll through
        if not self.pages:
            return

        if not self.scrolling:
            return await self.channel.send(embed=self.pages[0])

        self.message = await self.channel.send(embed=self.pages[0])
        for (reaction, _) in self.reaction_emojis:
            if len(self.pages) == 2 and reaction in ('\u23ed', '\u23ee'):
                continue

            await self.message.add_reaction(reaction)

    async def scroll(self, page):
        if page < 0 or page >= len(self.pages):
            return
        self.current_page = page
        await self.message.edit(embed=self.pages[page])

    async def first_page(self):
        await self.scroll(0)

    async def last_page(self):
        await self.scroll(len(self.pages) - 1)

    async def next_page(self):
        await self.scroll(self.current_page + 1)

    async def previous_page(self):
        await self.scroll(self.current_page - 1)

    async def stop_scrolling(self):
        self.scrolling = False
        if self.exit_delete:
            await self.message.delete()
            if self.clear_command:
                await self.cmdmsg.delete()

    def react_check(self, reaction, user):
        if user is None or user.id != self.author.id:
            return False

        if reaction.message.id != self.message.id:
            return False

        for (emoji, func) in self.reaction_emojis:
            if reaction.emoji == emoji:
                self.match = func
                return True
        return False

    async def start_scrolling(self):
        if not self.scrolling:
            await self.send()
        else:
            self.bot.loop.create_task(self.send())

        while self.scrolling:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', check=self.react_check, timeout=self.timeout)
            except asyncio.TimeoutError:
                self.scrolling = False
                try:
                    await self.message.clear_reactions()
                    if self.timeout_delete:
                        await self.message.delete()
                        if self.clear_command:
                            await self.cmdmsg.delete()
                except discord.Forbidden:
                    pass
                finally:
                    break

            try:
                await self.message.remove_reaction(reaction, user)
            except discord.Forbidden:
                pass

            await self.match()
