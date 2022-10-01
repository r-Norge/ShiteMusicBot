# Discord Packages
from discord.ext import commands

from ...utils.userinteraction.scroller import Scroller, ClearOn
from .helpformatter import coghelper, commandhelper, helper, prefix_cleaner


class Help(commands.Cog):
    """Help command"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def help(self, ctx):  # Takes no args because reasons(using the view directly)
        ctx.view.skip_ws()
        v = ctx.view
        invoker = v.buffer[v.index:v.end]
        ctx = self.bot.aliaser.get_subcommand(ctx, group=None, parents=[])
        command = v.buffer[v.index:v.end]

        ctx = prefix_cleaner(ctx)

        if not command:
            paginator = await helper(ctx)

        if command:
            thing = ctx.bot.get_cog(command) or ctx.bot.get_command(command)
            if not thing:
                return await ctx.send(ctx.localizer.format_str("{notcommand}", _command=command))
            if isinstance(thing, commands.Command):
                paginator = commandhelper(ctx, thing, invoker)
            else:
                paginator = await coghelper(ctx, thing)

        scroller = Scroller(ctx, paginator)
        await scroller.start_scrolling(ClearOn.Timeout | ClearOn.ManualExit)
