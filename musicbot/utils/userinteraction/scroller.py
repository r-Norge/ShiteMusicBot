import discord
from enum import Flag, auto

from lavalink.client import asyncio
from .paginators import BasePaginator, CantScrollException


class ScrollClearSettings(Flag):
    OnTimeout = auto()
    OnInteractionExit = auto()


class ScrollerButton(discord.ui.Button):
    def __init__(self, callback, label, style=discord.ButtonStyle.gray, **kwargs):
        super().__init__(label=label, style=style, **kwargs)
        self.callback = callback


class ScrollerNav(discord.ui.Select):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback


class Scroller:
    def __init__(self, ctx, paginator, clear_mode: ScrollClearSettings, timeout=20.0,
                 with_nav_bar: bool = True):

        if not isinstance(paginator, BasePaginator):
            raise TypeError('Paginator needs to be a subclass of BasePaginator.')

        self.clear_mode = clear_mode
        self.use_nav_bar = with_nav_bar
        self.paginator = paginator
        self.ctx = ctx

        # No embeds to scroll through
        if not self.paginator.pages:
            raise Exception("Paginator contained no pages to display")  # TODO: proper error

        self.bot = ctx.bot
        self.channel = ctx.channel
        self.message = None

        # Initialize the view we'll be using for scrolling
        self.view = discord.ui.View(timeout=timeout)
        self.view.on_timeout = self.on_timeout

        self.is_scrolling_paginator = len(self.paginator.pages) > 1
        self.scrolling_done = asyncio.Event()

        self.interaction_mapping = [
            ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.first_page),
            ('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
            ('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
            ('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.last_page),
            ('❌', self.stop),
        ]

        bot_user = ctx.guild if ctx.guild.me is not None else ctx.bot.user
        self.permissions = self.channel.permissions_for(bot_user)

        if not self.permissions.embed_links:
            raise CantScrollException('Bot does not have embed links permission.')

        if not self.permissions.send_messages:
            raise CantScrollException('Bot cannot send messages.')

    async def start_scrolling(self) -> discord.Message:
        self.current_page_number = 0
        self.build_view()

        if not self.is_scrolling_paginator:
            return await self.channel.send(embed=self.paginator.pages[0])

        self.message = await self.channel.send(embed=self.paginator.pages[0], view=self.view)
        await self.scrolling_done.wait()

        return self.message

    def update_view(self, interaction: discord.Interaction):
        self.navigator.placeholder = f"Page: {self.current_page_number + 1}/{len(self.paginator.pages)}"

    def build_view(self):
        for (reaction, callback) in self.interaction_mapping:
            self.view.add_item(item=ScrollerButton(callback=callback, label=reaction, row=3))

        if self.use_nav_bar:
            self.navigator = ScrollerNav(self.navigate, placeholder="Navigate to page", row=4)
            self.view.add_item(item=self.navigator)
            for (i, _) in enumerate(self.paginator.pages):
                self.navigator.add_option(label=str(i+1), value=str(i))

    async def stop(self, user_stopped: bool):
        self.is_scrolling_paginator = False
        self.view.stop()
        self.view.clear_items()
        if (user_stopped and self.clear_mode & ScrollClearSettings.OnInteractionExit or
                not user_stopped and self.clear_mode & ScrollClearSettings.OnTimeout):
            await self.message.delete()
            self.message = None
            await self.ctx.message.delete()
        else:
            await self.message.edit(embed=self.paginator.pages[self.current_page_number])

        # Notify the start_scrolling function that we're done
        self.scrolling_done.set()

    async def _scroll(self, page, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.defer()

        if page < 0 or page >= len(self.paginator.pages):
            return
        self.current_page_number = page

        if interaction.message:
            # Update the view before we edit the message
            self.update_view(interaction)
            await interaction.message.edit(embed=self.paginator.pages[page], view=self.view)
        await interaction.response.defer()

    async def first_page(self, interaction: discord.Interaction):
        await self._scroll(0, interaction)

    async def last_page(self, interaction: discord.Interaction):
        await self._scroll(len(self.paginator.pages) - 1, interaction)

    async def next_page(self, interaction: discord.Interaction):
        await self._scroll(self.current_page_number + 1, interaction)

    async def previous_page(self, interaction: discord.Interaction):
        await self._scroll(self.current_page_number - 1, interaction)

    async def navigate(self, interaction: discord.Interaction):
        await self._scroll(int(self.navigator.values[0]), interaction)

    async def stop_scrolling(self, _: discord.Interaction):
        await self.stop(user_stopped=True)

    async def on_timeout(self):
        await self.stop(user_stopped=False)
