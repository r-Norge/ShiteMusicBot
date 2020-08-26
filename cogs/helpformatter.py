# Discord Packages
from discord.ext import commands

import re

# Bot Utilities
from cogs.utils.paginator import HelpPaginator, Scroller

usermention = r"<@!?\d{17,19}>"


def get_cmd_dict(ctx, qualified_name):
    split = qualified_name.split()
    cmd_dict = ctx.bot.aliaser.get_cmd_help(ctx.locale, split[-1], split[:-1])

    # Fallback for new commands and missing translations
    if not cmd_dict:
        cmd_dict = ctx.bot.aliaser.get_cmd_help("en_en", split[-1], split[:-1])
        try:
            cmd_dict["aliases"] = [split[-1]]
        except KeyError:
            cmd_dict = None
    return cmd_dict


async def helper(ctx):
    bot = ctx.bot
    # Display music commands first
    music = bot.get_cog('Music')
    paginator = await coghelper(ctx, music)

    for cog in bot.cogs.copy().values():
        if cog.__cog_name__ == 'Music':
            continue
        cogpaignator = await coghelper(ctx, cog)
        paginator.append_paginator(cogpaignator)

    paginator.add_page_indicator(ctx.localizer, "{pageindicator}", _prefix=ctx.prefix)
    return paginator


async def coghelper(ctx, cog, ignore_subcommands=True):
    paginator = HelpPaginator(max_size=5000, max_fields=5, color=ctx.me.color, title=cog.__cog_name__)
    for cmd in cog.walk_commands():
        if ignore_subcommands:
            if len(cmd.qualified_name.split()) > 1:
                continue
        if cmd.hidden:
            continue
        try:
            can_run = await cmd.can_run(ctx)
        except commands.CommandError:  # Was 'CommandError' guessed it was supposed to be what it is now
            can_run = False
        if not can_run:
            continue
        cmd_dict = get_cmd_dict(ctx, cmd.qualified_name)
        if cmd_dict:
            paginator.add_command_field(cmd_dict)

    paginator.add_page_indicator(ctx.localizer, "{pageindicator}", _prefix=ctx.prefix)
    return paginator


def commandhelper(ctx, command, invoker, include_subcmd=True):
    cmd_dict = get_cmd_dict(ctx, command.qualified_name)
    command_depth = len(command.qualified_name.split()) - 1

    prefix = ctx.prefix
    if invoker.split()[:command_depth]:
        prefix += ' '.join(invoker.split()[:command_depth]) + ' '

    aliases = cmd_dict.get('aliases', [])
    args = cmd_dict.get('args', '')
    description = cmd_dict.get('description', '')
    sub_commands = cmd_dict.get('sub_commands', [])

    if len(aliases) > 1:
        cmd = prefix + '[' + '|'.join([str(a) for a in aliases]) + '] '
    else:
        cmd = prefix + '|'.join([str(a) for a in aliases]) + ' '

    cmd += args
    if not sub_commands or not include_subcmd:
        paginator = HelpPaginator(max_size=5000, max_fields=5, color=ctx.me.color, title=cmd, description=description)
        paginator.force_close_page()
        return paginator

    description = f"```{description}```"
    paginator = HelpPaginator(max_size=5000, max_fields=5, color=ctx.me.color, title=cmd, description=description)

    for sub_command, sub_cmd_dict in sub_commands.items():
        paginator.add_command_field(sub_cmd_dict)
    paginator.add_page_indicator(ctx.localizer, "{pageindicator}", _prefix=ctx.prefix)
    return paginator


def prefix_cleaner(ctx):
    """ Changes mentions to prefixes when commands are invoked with mentions."""
    bot = ctx.bot
    prefix = ctx.prefix
    if re.match(usermention, prefix):
        if not ctx.guild:
            pref = bot.settings.default_prefix
        else:
            pref = bot.settings.get(ctx.guild, 'prefixes', 'default_prefix')
        if isinstance(pref, list):
            pref = pref[0]
        ctx.prefix = pref
    return ctx


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
        await scroller.start_scrolling()


def setup(bot):
    bot.remove_command("help")
    bot.add_cog(Help(bot))
