from __future__ import annotations

# Discord Packages
import discord

import asyncio
from enum import Flag, auto
from typing import List, Optional

from bot import MusicBot

from .paginators import BasePaginator, CantScrollException


class ClearOn(Flag):
    Timeout = auto()
    ManualExit = auto()
    AnyExit = Timeout | ManualExit


class ScrollerButton(discord.ui.Button):
    def __init__(self, callback, label, style=discord.ButtonStyle.gray, **kwargs):
        super().__init__(label=label, style=style, **kwargs)
        self.callback = callback


class ScrollerNav(discord.ui.Select):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback


class Scroller:
    def __init__(self, ctx, paginator, timeout=20.0, use_tick_for_stop_emoji: bool = False,
                 show_cancel_for_single_page: bool = False):

        if not isinstance(paginator, BasePaginator):
            raise TypeError('Paginator needs to be a subclass of BasePaginator.')

        self.paginator = paginator
        self.ctx = ctx

        # No embeds to scroll through
        if not self.paginator.pages:
            raise Exception("Paginator contained no pages to display")  # TODO: proper error

        self.bot: MusicBot = ctx.bot
        self.channel = ctx.channel
        self.message: Optional[discord.Message] = None

        # Initialize the view we'll be using for scrolling
        self.view = discord.ui.View(timeout=timeout)
        self.view.on_timeout = self.on_timeout

        self.is_scrolling_paginator = len(self.paginator.pages) > 1
        self.use_nav_bar = len(self.paginator.pages) > 3
        self.scrolling_done = asyncio.Event()

        stop_emoji = '✔️' if use_tick_for_stop_emoji else '❌'

        self.control_buttons: List[ScrollerButton] = []

        self.forward_button = ScrollerButton(self.next_page, '\N{BLACK RIGHT-POINTING TRIANGLE}', row=3)
        self.back_button = ScrollerButton(self.previous_page, '\N{BLACK LEFT-POINTING TRIANGLE}', row=3)
        first_page_button = ScrollerButton(self.first_page,
                                           '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', row=3)
        last_page_button = ScrollerButton(self.last_page,
                                          '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', row=3)
        self.stop_button = ScrollerButton(self.stop, stop_emoji, row=3)

        # We start on the first page, can't go back
        self.back_button.disabled = True

        # Determine which buttons should be visible depending on the number of pages
        if (self.is_scrolling_paginator):
            if (len(self.paginator.pages) > 2):
                self.control_buttons = [first_page_button, self.back_button, self.forward_button,
                                        last_page_button, self.stop_button]
            else:
                self.control_buttons = [self.back_button, self.forward_button, self.stop_button]
        elif show_cancel_for_single_page:
            self.control_buttons = [self.stop_button]

        bot_user = ctx.guild if ctx.guild.me is not None else ctx.bot.user
        self.permissions = self.channel.permissions_for(bot_user)

        if not self.permissions.embed_links:
            raise CantScrollException('Bot does not have embed links permission.')

        if not self.permissions.send_messages:
            raise CantScrollException('Bot cannot send messages.')

    async def start_scrolling(self, clear_mode: ClearOn,
                              message: Optional[discord.Message] = None,
                              start_page: int = 0) -> discord.Message:
        self.clear_mode = clear_mode
        self.page_number = start_page
        self.build_view()
        self.update_view()
        if message:
            self.message = message
            await self.message.edit(embed=self.current_page_embed, view=self.view)
        else:
            self.message = await self.channel.send(embed=self.current_page_embed, view=self.view)
        await self.scrolling_done.wait()
        return self.message

    def update_view_on_interaction(self, interaction: discord.Interaction):
        self.update_view()

    def update_view(self):
        if self.use_nav_bar:
            self.navigator.placeholder = f"Page: {self.page_number + 1}/{len(self.paginator.pages)}"

        if self.is_scrolling_paginator:
            self.back_button.disabled = self.page_number == 0
            self.forward_button.disabled = self.page_number == len(self.paginator.pages)-1

    def build_view(self):
        for button in self.control_buttons:
            self.view.add_item(item=button)

        if self.use_nav_bar:
            self.navigator = ScrollerNav(self.navigate, placeholder="Navigate to page", row=4)
            self.view.add_item(item=self.navigator)
            for (i, _) in enumerate(self.paginator.pages):
                self.navigator.add_option(label=str(i+1), value=str(i))

    async def stop(self, user_stopped: bool, clear_scroller_view: bool = True):
        self.is_scrolling_paginator = False
        self.view.stop()
        if clear_scroller_view:
            self.view.clear_items()
        if (user_stopped and self.clear_mode & ClearOn.ManualExit or
                not user_stopped and self.clear_mode & ClearOn.Timeout):
            if self.message:
                await self.message.delete()
                self.message = None
            # If this fails the message is not accessable either way, which
            # means it is probably deleted
            try:
                if self.ctx.message:
                    await self.ctx.message.delete()
            except discord.HTTPException:
                pass
        else:
            if clear_scroller_view:
                await self.update_message()

        # Notify the start_scrolling function that we're done
        self.scrolling_done.set()

    async def _scroll(self, page, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.defer()

        if page < 0 or page >= len(self.paginator.pages):
            return
        self.page_number = page

        if interaction.message:
            # Update the view before we edit the message
            self.update_view_on_interaction(interaction)
            await self.update_message()
        await interaction.response.defer()

    async def update_message(self):
        if self.message:
            await self.message.edit(embed=self.current_page_embed, view=self.view)

    async def first_page(self, interaction: discord.Interaction):
        await self._scroll(0, interaction)

    async def last_page(self, interaction: discord.Interaction):
        await self._scroll(len(self.paginator.pages) - 1, interaction)

    async def next_page(self, interaction: discord.Interaction):
        await self._scroll(self.page_number + 1, interaction)

    async def previous_page(self, interaction: discord.Interaction):
        await self._scroll(self.page_number - 1, interaction)

    async def navigate(self, interaction: discord.Interaction):
        await self._scroll(int(self.navigator.values[0]), interaction)

    async def stop_scrolling(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.stop(user_stopped=True)

    async def on_timeout(self):
        await self.stop(user_stopped=False)

    @property
    def current_page_embed(self):
        return self.paginator.pages[self.page_number]
