from __future__ import annotations

# Discord Packages
import discord
import asyncio
import inspect

from typing import Callable, Coroutine, List

from .paginators import TextPaginator
from .scroller import ClearOn, Scroller


class SelectorButton(discord.ui.Button):
    def __init__(self, label, callback: Callable[[discord.Interaction, SelectorButton], Coroutine],
                 style=discord.ButtonStyle.gray, **kwargs):
        super().__init__(label=label, style=style, **kwargs)

        # The callback we need to supply to disord.py takes only a discord.Interaction
        # we want to have access to the button that was clicked (self)
        # so we can update or modify it upon it being pressed i.e. change color.
        def add_button_to_callback(func):
            async def wrapped_callback(interaction: discord.Interaction):
                await func(interaction, self)
            return wrapped_callback

        self.callback = add_button_to_callback(callback)


class SelectorItem:
    def __init__(self, identifier, button_label, callback: Callable[[discord.Interaction, SelectorButton], Coroutine]):
        self.button_label = button_label
        self.identifier = identifier
        self.callback = callback


class Selector2(TextPaginator, Scroller):
    def __init__(self, ctx, choices: List[SelectorItem], round_titles=None, use_tick_for_stop_emoji: bool = False,
                 terminate_on_select: bool = True, max_size=2000, default_text=" ", **embed_base):
        self.match = None
        if round_titles is None:
            round_titles = []
        self.match = None
        self.terminate_on_select = terminate_on_select
        self.round_titles = round_titles

        self.selections_per_page = 5
        self.selections = choices

        TextPaginator.__init__(self, max_size=max_size, max_lines=self.selections_per_page, **embed_base)
        for selection in self.selections:
            if (selection.identifier):
                self.add_line(selection.identifier)
        if len(self.pages) == 0:
            self.add_line(default_text)
        self.close_page()

        Scroller.__init__(self, ctx, self, use_tick_for_stop_emoji=use_tick_for_stop_emoji,
                          show_cancel_for_single_page=True)

        # Contains a list of all buttons that can be interacted with, both
        # currently visible and not.
        self.buttons = []

        # The list of currently visible buttons, gets cleared upon scroll.
        self.visible_buttons = []

        # Depending on the selector we might want the result of callbacks
        # after we have finished interacting with the scroller
        self.callback_results = []

        # Wrap the provided so that we can both update the view if needed
        # or terminate the selection process upon interaction
        def with_update_view(func):
            async def wrapped_callback(interaction: discord.Interaction, button: SelectorButton):
                if (interaction.user.id != ctx.author.id):
                    return await interaction.response.defer()

                result = await func(interaction, button)
                self.callback_results.append(result)
                self.update_view(interaction)
                await interaction.response.defer()
                if terminate_on_select:
                    await self.stop(True)
                else:
                    await self.update_message()
            return wrapped_callback

        for choice in self.selections:
            self.buttons.append(SelectorButton(choice.button_label, with_update_view(choice.callback), row=0))

    def build_view(self):
        super().build_view()
        self.update_buttons()

    def update_view(self, interaction: discord.Interaction):
        super().update_view(interaction)
        self.update_buttons()

    def update_buttons(self):
        for button in self.visible_buttons:
            self.view.remove_item(item=button)

        self.visible_buttons = []
        self.current_page_number
        start = self.current_page_number * self.selections_per_page
        end = min((self.current_page_number + 1) * self.selections_per_page, len(self.selections))

        for button in self.buttons[start:end]:
            self.view.add_item(item=button)
            self.visible_buttons.append(button)

    async def start_scrolling(self, clear_mode: ClearOn = ClearOn.Timeout):
        message = await super().start_scrolling(clear_mode)
        return message, self.callback_results


class Selector(TextPaginator):
    def __init__(self, ctx, identifiers, functions, arguments, terminate_on_select=True, num_selections=3,
                 round_titles=None, max_size=2000, **embed_base):
        """
        Selector, tool for making interactive menus.
        :param ctx: discord.py context
        :param identifiers: A list of strings, one for each menu item
        :param functions: List of functions, one for each menu item. Gets run when the corresponding
                          menu item is selected
        :param arguments: List of arguments to pass to the corresponding function in functions.
        :param terminate_on_select:
        :param num_selections: the number of selectable items per page
        :param round_titles: A list of embed titles, updates each time a menu selection is made
        :param max_size: The max amount of characters per page.
        :param embed_base: Arguments that specify the look of the scroller embeds
        """
        if round_titles is None:
            round_titles = []
        self.match = None
        self.current_page = 0
        self.ctx = ctx
        self.bot = ctx.bot
        self.cmdmsg = ctx.message
        self.message = ctx.message
        self.channel = ctx.channel
        self.author = ctx.author

        self.localizer = ctx.localizer

        self.num_selections = num_selections
        self.terminate_on_select = terminate_on_select
        self.round_titles = round_titles

        assert len(identifiers) == len(functions) == len(arguments)
        super().__init__(max_size=max_size, max_lines=num_selections, **embed_base)

        self.selections = list(zip(identifiers, functions, arguments))

        self.max_selections = min(len(identifiers), num_selections)
        for i, selection in enumerate(self.selections):
            self.add_line(f"{i%num_selections+1}\N{combining enclosing keycap} {selection[0]}")
        self.close_page()

        if len(self.pages) > 1:
            self.multipage = True
        else:
            self.multipage = False

        assert num_selections <= 10
        self.select_emojis = [f"{i+1}\N{combining enclosing keycap}" for i in range(num_selections)]

        self.control_emojis = [
            ('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
            ('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
            ('❌', self.stop_scrolling),
        ]

        self.timeout = 30
        self.args = None
        self.control_input = False
        self.scrolling = True
        self.stopped = False

        self.add_page_indicator(self.localizer, "{queue.pageindicator}")
        if self.round_titles:
            self.update_embed_title(self.round_titles.pop(0))

    async def scroll(self, page):
        if page < 0 or page >= len(self.pages):
            return
        self.current_page = page
        await self.message.edit(embed=self.pages[page])

    async def next_page(self):
        await self.scroll(self.current_page + 1)

    async def previous_page(self):
        await self.scroll(self.current_page - 1)

    async def stop_scrolling(self):
        self.scrolling = False
        await self.message.clear_reactions()

    def update_embed_title(self, updated_title):
        for page in self.pages:
            page.title = updated_title

    def _react_check(self, reaction, user):
        if user is None or user.id != self.author.id:
            return False

        if reaction.message.id != self.message.id:
            return False

        for i, emoji in enumerate(self.select_emojis):
            if emoji == reaction.emoji:
                choice = i + self.current_page * self.num_selections
                if choice >= len(self.selections):
                    return True
                self.match = self.selections[choice][1]
                self.args = self.selections[choice][2]
                return True

        for (emoji, func) in self.control_emojis:
            if reaction.emoji == emoji:
                self.match = func
                self.control_input = True
                return True
        return False

    async def send(self):
        # No embeds to scroll through
        if not self.pages:
            return

        self.message = await self.channel.send(embed=self.pages[0])

        for reaction in self.select_emojis[:self.max_selections]:
            if not self.stopped:
                await self.message.add_reaction(reaction)

        if self.multipage:
            for reaction in list(zip(*self.control_emojis))[0]:
                if not self.stopped:
                    await self.message.add_reaction(reaction)
        else:
            if not self.stopped:
                await self.message.add_reaction('❌')

    async def start_scrolling(self):
        result = None
        if not self.scrolling:
            await self.send()
        else:
            self.bot.loop.create_task(self.send())

        current_round = 0
        results = []
        while self.scrolling:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', check=self._react_check, timeout=self.timeout)
            except asyncio.TimeoutError:
                self.scrolling = False
                try:
                    await self.message.clear_reactions()
                except (discord.Forbidden, discord.HTTPException):
                    pass
                finally:
                    break

            try:
                await self.message.remove_reaction(reaction, user)
            except (discord.Forbidden, discord.HTTPException, discord.NotFound, discord.InvalidArgument):
                pass
            if self.match:
                if inspect.iscoroutinefunction(self.match):
                    if self.args:
                        result = await self.match(*self.args)
                    else:
                        result = await self.match()
                else:
                    if self.args:
                        result = self.match(*self.args)
                    else:
                        result = self.match()
            else:
                continue

            if self.terminate_on_select and not self.control_input:
                current_round += 1
                results.append(result)
                if not self.round_titles:
                    self.stopped = True
                    try:
                        await self.message.clear_reactions()
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                    break
                if self.round_titles:
                    self.update_embed_title(self.round_titles.pop(0))
                    await self.scroll(self.current_page)
            self.args = None
            self.control_input = False
        if len(results) == 1:
            self.stopped = True
            await self.message.clear_reactions()
            return self.message, self.pages[self.current_page], results[0]
        else:
            self.stopped = True
            await self.message.clear_reactions()
            return self.message, self.pages[self.current_page], results
