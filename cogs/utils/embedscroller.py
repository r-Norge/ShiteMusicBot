import asyncio
import discord
import math
import lavalink

class CantScroll(Exception):
    pass

# Maybe slightly very copied from rdanny
# Thanks danny <3

class EmbedScroller:
    def __init__(self, ctx, pages):

        self.bot = ctx.bot
        self.pages = pages
        self.cmdmsg = ctx.message
        self.message = ctx.message
        self.channel = ctx.channel
        self.author = ctx.author

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
        await self.message.delete()
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
                reaction, user = await self.bot.wait_for('reaction_add', check=self.react_check, timeout=120.0)
            except asyncio.TimeoutError:
                self.scrolling = False
                try:
                    await self.message.clear_reactions()
                except:
                    pass
                finally:
                    break

            try:
                await self.message.remove_reaction(reaction, user)
            except:
                pass

            await self.match()


class ScrollerFromLines(EmbedScroller):
    def __init__(self, ctx, description, lines, lines_per_page=10):
        pagecount = math.ceil(len(lines) / lines_per_page)
        pages = []
        page = ''
        for index, line in enumerate(lines):
            page += line + '\n'
            if index%lines_per_page == lines_per_page - 1:
                embed = discord.Embed(color=0xEFD26C,
                                title=description,
                                description=page)
                embed.set_footer(text=f'Viewing page {index//lines_per_page}/{pagecount}')
                pages.append(embed)
                page = ''

        if page != '':
            embed = discord.Embed(color=0xEFD26C,
                            description=page)

            embed.set_footer(text=f'Viewing page {pagecount}/{pagecount}')
            pages.append(embed)

        super().__init__(ctx=ctx, pages=pages)


class QueueScroller(EmbedScroller):
    """ Fugly, but works for now """
    def __init__(self, ctx, queue, lines_per_page=10, user_name: str=None):

        pagecount = math.ceil(len(queue) / lines_per_page)
        self.queue = queue

        if user_name is None:
            title = f'**Queue** `{len(queue)} songs`'
        else:
            title = f'**{user_name}\'s queue** `{len(queue)} songs`'
        pages = []
        page = ''
        for index, temp in enumerate(queue):
            if user_name is None:
                track = temp
                page += f'`{index + 1}.` **[{track.title}]({track.uri})** _by <@{track.requester}>_\n'
            else:
                track, globpos = temp
                page += f'`{index + 1}({globpos + 1}).` **[{track.title}]({track.uri})**\n'

            if index%lines_per_page == lines_per_page - 1:
                embed = discord.Embed(color=0xEFD26C,
                                title=title,
                                description=page)
                embed.set_footer(text=f'Viewing page {index//lines_per_page + 1}/{pagecount}')
                pages.append(embed)
                page = ''

        if page != '':
            embed = discord.Embed(color=0xEFD26C,
                            title=title,
                            description=page)
            embed.set_footer(text=f'Viewing page {pagecount}/{pagecount}')
            pages.append(embed)

        super().__init__(ctx=ctx, pages=pages)

    async def scroll(self, page):
        # overwrite to add ability to update queue length/add scrubber.
        if page < 0 or page >= len(self.pages):
            return
        self.current_page = page
        await self.message.edit(embed=self.pages[page])