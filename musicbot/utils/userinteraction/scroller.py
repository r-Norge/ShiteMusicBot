import discord
from enum import Flag, auto
from .paginators import BasePaginator, CantScrollException

class ScrollerButton(discord.ui.Button):
    def __init__(self, method, label, style=discord.ButtonStyle.gray):
        super().__init__(label=label, style=style)
        self.callback = method

class ScrollClearSettings(Flag):
    OnTimeout = auto()
    OnInteractionExit = auto()

class Scroller:
    def __init__(self, ctx, paginator, timeout=20.0, clear_mode: ScrollClearSettings = ScrollClearSettings.OnInteractionExit):
        if not isinstance(paginator, BasePaginator):
            raise TypeError('Paginator needs to be a subclass of BasePaginator.')

        self.bot = ctx.bot
        self.pages = paginator.pages
        self.cmdmsg = ctx.message
        self.message = ctx.message
        self.channel = ctx.channel
        self.author = ctx.author

        # Initialize the view we're using for scrolling
        self.view = discord.ui.View(timeout=timeout)
        self.view.on_timeout = self.on_timeout 
        
        self.clear_mode = clear_mode

        if len(self.pages) > 1:
            self.scrolling = True
        else:
            self.scrolling = False

        self.interaction_mapping = [
            ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.first_page),
            ('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
            ('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
            ('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.last_page),
            ('❌', self.stop),
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
            if not self.permissions.read_message_history:
                raise CantScrollException('Bot does not have Read Message History permission.')

    async def start_scrolling(self):
        self.current_page_number = 0
        # No embeds to scroll through
        if not self.pages:
            return

        if not self.scrolling:
            return await self.channel.send(embed=self.pages[0])

        for (reaction, callback) in self.interaction_mapping:
            self.view.add_item(item=ScrollerButton(callback, label=reaction))
        self.message = await self.channel.send(embed=self.pages[0], view=self.view)

    async def stop(self, user_stopped: bool):
        self.scrolling = False
        self.view.stop()
        self.view.clear_items()
        if user_stopped and self.clear_mode & ScrollClearSettings.OnInteractionExit or \
            not user_stopped and self.clear_mode & ScrollClearSettings.OnTimeout:
            await self.message.delete()
            await self.cmdmsg.delete()
        else:
            await self.message.edit(embed=self.pages[self.current_page_number], view=self.view)

    async def scroll(self, page, interaction: discord.Interaction):
        if page < 0 or page >= len(self.pages):
            return
        self.current_page_number = page
        if interaction.message:
            await interaction.message.edit(embed=self.pages[page], view=self.view)
        await interaction.response.defer()

    async def first_page(self, interaction: discord.Interaction):
        await self.scroll(0, interaction)

    async def last_page(self, interaction: discord.Interaction):
        await self.scroll(len(self.pages) - 1, interaction)

    async def next_page(self, interaction: discord.Interaction):
        await self.scroll(self.current_page_number + 1, interaction)

    async def previous_page(self, interaction: discord.Interaction):
        await self.scroll(self.current_page_number - 1, interaction)

    async def stop_scrolling(self, _: discord.Interaction):
        await self.stop(user_stopped=True)

    async def on_timeout(self):
        await self.stop(user_stopped=False)

