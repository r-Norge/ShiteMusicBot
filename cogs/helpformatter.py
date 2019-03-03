# NOTICE: Before you copy this example, be sure you understand what all this does. Remember: This is a gist, not a github file meaning
# you can't pip install this, you would need to put this into a new file and add it to your cog list.

import pprint

import discord
import asyncio
from discord.ext import commands

from cogs.utils.paginator import HelpPaginator, Scroller


def get_cmd_dict(ctx, qualified_name):
    split = qualified_name.split()
    cmd_dict = ctx.bot.aliaser.get_cmd_help(ctx.locale, split[-1], split[:-1])
    return cmd_dict


def helper(ctx):
    bot = ctx.bot
    # Display music commands first
    music = bot.get_cog('Music')
    paginator = coghelper(ctx, music)

    for cog in bot.cogs.copy().values():
        if cog.__cog_name__ is 'Music':
            continue
        cogpaignator = coghelper(ctx, cog)
        paginator.append_paginator(cogpaignator)

    paginator.add_page_indicator(ctx.localizer, "{pageindicator}", ctx.prefix)
    return paginator


def coghelper(ctx, cog, ignore_subcommands=True):
    paginator = HelpPaginator(max_size=5000, max_fields=5, color=ctx.me.color, title=cog.__cog_name__)
    for cmd in cog.walk_commands():
        if ignore_subcommands:
            if len(cmd.qualified_name.split()) > 1:
                continue
        if cmd.hidden:
            continue
        cmd_dict = get_cmd_dict(ctx, cmd.qualified_name)
        paginator.add_command_field(cmd_dict)
    paginator.add_page_indicator(ctx.localizer, "{paginator}", ctx.prefix)
    return paginator


def commandhelper(ctx, command, invoker, include_subcmd=True):
    cmd_dict = get_cmd_dict(ctx, command.qualified_name)
    prefix = ctx.prefix
    if invoker.split()[:-1]:
        prefix += ' '.join(invoker.split()[:-1]) + ' '

    aliases = cmd_dict.get('aliases', [])
    args = cmd_dict.get('args', '')
    description = cmd_dict.get('description', '')
    sub_commands = cmd_dict.get('sub_commands', [])

    if len(aliases) > 1:
        cmd = prefix + '[' + '|'.join([str(a) for a in aliases]) + '] '
    else:
        cmd = prefix + '|'.join([str(a) for a in aliases]) + ' '

    cmd += args
    if not sub_commands:
        paginator = HelpPaginator(max_size=5000, max_fields=5, color=ctx.me.color, title=cmd, description=description)
        paginator.force_close_page()
        return paginator

    description = f"```{description}```"
    paginator = HelpPaginator(max_size=5000, max_fields=5, color=ctx.me.color, title=cmd, description=description)

    for sub_command, sub_cmd_dict in sub_commands.items():
        paginator.add_command_field(sub_cmd_dict)
    paginator.add_page_indicator(ctx.localizer, "{pageindicator}", ctx.prefix)
    return paginator


class Help(commands.Cog):
    """Help command"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def help(self, ctx): # Takes no args because reasons(using the view directly)
        ctx.view.skip_ws()
        v = ctx.view
        invoker = v.buffer[v.index:v.end]
        ctx = self.bot.aliaser.get_subcommand(ctx, group=None, parents=[])
        command = v.buffer[v.index:v.end]

        if not command:
            scroller = Scroller(ctx, helper(ctx))
            await scroller.start_scrolling()

        if command:
            thing = ctx.bot.get_cog(command) or ctx.bot.get_command(command)
            if not thing:
                return await ctx.send(f'Looks like "{command}" is not a command or category.')
            if isinstance(thing, commands.Command):
                paginator = commandhelper(ctx, thing, invoker)
                scroller = Scroller(ctx, paginator)
                await scroller.start_scrolling()
            else:
                scroller = Scroller(ctx, coghelper(ctx, thing))
                await scroller.start_scrolling()

def setup(bot):
    bot.remove_command("help")
    bot.add_cog(Help(bot))