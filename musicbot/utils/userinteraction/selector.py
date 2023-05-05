from __future__ import annotations

from enum import Enum, auto
from typing import Callable, Coroutine, List, Optional

import discord

from .paginators import TextPaginator
from .scroller import ClearMode, Scroller


def selector_button_callback(f):
    def wrapper(*args, **kwargs):
        async def base_button_callback(_interaction, _button):
            # call the decorated function f with provided args and button info
            return await f(_interaction, _button, *args, **kwargs)
        return base_button_callback
    return wrapper


class SelectMode(Enum):
    SingleSelect = auto()
    MultiSelect = auto()
    SpanningMultiSelect = auto()  # Used to keep the view around after select


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


class Selector(TextPaginator, Scroller):
    def __init__(self, ctx, choices: List[SelectorItem], select_mode: SelectMode,
                 use_tick_for_stop_emoji: bool = False, max_size=2000, default_text=" ", **embed_base):

        self.selector_mode: SelectMode = select_mode

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
        self.currently_visible_buttons = []

        # Depending on the selector we might want the result of calculations in
        # the callbacks after we have finished interacting with the scroller
        self.callback_results = []

        # Wrap the provided so that we can both update the view if needed
        # or terminate the selection process upon interaction
        def with_update_view(func):
            async def wrapped_callback(interaction: discord.Interaction, button: SelectorButton):
                if (interaction.user.id != ctx.author.id):
                    return await interaction.response.defer()

                result = await func(interaction, button)
                self.callback_results.append(result)
                self.update_view_on_interaction(interaction)
                await interaction.response.defer()

                match self.selector_mode:
                    case SelectMode.SingleSelect:
                        await self.stop(was_timeout=False, clear_scroller_view=True)
                    case SelectMode.SpanningMultiSelect:
                        await self.stop(was_timeout=False, clear_scroller_view=False)
                    case _:
                        await self.update_message()

            return wrapped_callback

        for choice in self.selections:
            self.buttons.append(SelectorButton(choice.button_label, with_update_view(choice.callback), row=0))

    def build_view(self):
        super().build_view()
        self.update_buttons()

    def update_view(self):
        super().update_view()
        self.update_buttons()

    def update_buttons(self):
        for button in self.currently_visible_buttons:
            self.view.remove_item(item=button)

        self.currently_visible_buttons = []
        start = self.page_number * self.selections_per_page
        end = min((self.page_number + 1) * self.selections_per_page, len(self.selections))

        for button in self.buttons[start:end]:
            self.view.add_item(item=button)
            self.currently_visible_buttons.append(button)

    async def start_scrolling(self, clear_mode: ClearMode = ClearMode.Timeout,
                              message: Optional[discord.Message] = None,
                              start_page: int = 0):
        message, timed_out = await super().start_scrolling(clear_mode, message, start_page)
        return message, timed_out, self.callback_results
