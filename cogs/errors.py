# Discord Packages
import discord
from discord.ext import commands

import traceback

# Bot Utilities
from cogs.helpformatter import commandhelper
from cogs.utils.paginator import Scroller


class Errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = self.bot.main_logger.bot_logger.getChild("Errors")

    async def base_msg(self, ctx, state: int = 0xFCBA03):
        embed = discord.Embed(color=state)
        embed.title = '{errors.error_occurred}'
        embed.set_footer(icon_url=ctx.author.avatar_url,
                         text=f'{ctx.author.name}#{ctx.author.discriminator}')
        return embed

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        ignored = (commands.CommandNotFound)

        if isinstance(err, ignored):
            return

        if isinstance(err, commands.CommandInvokeError) and (err.original == 'Join a voicechannel first.'):
            embed = await self.base_msg(ctx, state=0xFC0303)
            embed.description = '{errors.join_voice_first}'
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)
        elif isinstance(err, commands.CommandInvokeError) and (err.original == 'Not connected.'):
            embed = await self.base_msg(ctx, state=0xFC0303)
            embed.description = '{errors.not_connected}'
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)
        elif isinstance(err, commands.CommandInvokeError) and (err.original ==
                                                               'I need the `CONNECT` and `SPEAK` permissions.'):
            embed = await self.base_msg(ctx, state=0xFC0303)
            embed.description = '{errors.need_permission}'
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)
        elif isinstance(err, commands.CommandInvokeError) and (err.original ==
                                                               'You need to be in the right voice channel'):
            embed = await self.base_msg(ctx, state=0xFC0303)
            embed.description = '{errors.right_channel}'
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)
        elif isinstance(err, commands.CommandInvokeError) and (err.original == 'You need to be in my voicechannel.'):
            embed = await self.base_msg(ctx, state=0xFC0303)
            embed.description = '{errors.my_channel}'
            embed = ctx.localizer.format_embed(embed)
            return await ctx.send(embed=embed)
        if not self.bot.debug:
            if (isinstance(err, commands.MissingRequiredArgument) or
                    isinstance(err, commands.BadArgument)):
                paginator = commandhelper(ctx, ctx.command, ctx.invoker, include_subcmd=False)
                scroller = Scroller(ctx, paginator)
                await scroller.start_scrolling()

            if isinstance(err, commands.CommandInvokeError):
                self.logger.debug(
                    "Error running command: %s\nTraceback: %s" % (ctx.command, err))
                pass

            elif isinstance(err, commands.NoPrivateMessage):
                self.logger.debug("Error running command: %s\nTraceback: %s" % (ctx.command, err))
                await ctx.send('That command is not available in DMs')

            elif isinstance(err, commands.CommandOnCooldown):
                await ctx.send(f"{ctx.message.author.mention} Command is on cooldown. "
                               f"Try again in `{err.retry_after:.1f}` seconds.")

            elif isinstance(err, RuntimeError):
                self.logger.debug("Error running command: %s\nTraceback: %s" % (ctx.command, err))
                pass

            elif isinstance(err, commands.CheckFailure):
                self.logger.debug("Error running command: %s\nTraceback: %s" % (ctx.command, err))
                pass

            elif isinstance(err, commands.CommandNotFound):
                pass
        else:
            tb = err.__traceback__
            traceback.print_tb(tb)
            print(err)
            self.logger.debug("Error running command: %s\nTraceback: %s" % (ctx.command, err))


def setup(bot):
    bot.add_cog(Errors(bot))
