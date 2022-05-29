
# This was at some point *heavliy* inspired by the paginator implementation by Rapptz for r.Danny
# https://github.com/Rapptz/RoboDanny/blob/b0401e046814f42597c6e0280fef2432cc49cc5d/cogs/utils/paginator.py

import discord
import asyncio

from .paginators import BasePaginator, CantScrollException


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
            raise CantScrollException('Bot does not have embed links permission.')

        if not self.permissions.send_messages:
            raise CantScrollException('Bot cannot send messages.')

        if self.scrolling:
            # verify we can actually use the pagination session
            if not self.permissions.add_reactions:
                raise CantScrollException('Bot does not have add reactions permission.')

            if not self.permissions.read_message_history:
                raise CantScrollException('Bot does not have Read Message History permission.')

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
