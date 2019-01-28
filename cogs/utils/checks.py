import discord
from discord.ext import commands


async def check_guild_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return False

    resolved = ctx.author.guild_permissions
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


def has_role(ctx, role):
    if ctx.channel is discord.DMChannel:
        return False

    role = discord.utils.get(ctx.author.roles, name=role)
    return role is not None


def has_guild_permissions(*, check=all, **perms):
    async def pred(ctx):
        return await check_guild_permissions(ctx, perms, check=check)
    return commands.check(pred)


def is_even():
    def predicate(ctx):
        return ctx.message.author.id == 142212883512557569
    return commands.check(predicate)


def is_owner():
    def predicate(ctx):
        is_owner = (ctx.message.author.id == 120970603556503552 or
            ctx.message.author.id == 142212883512557569 or ctx.message.author.id == 212635519706726410)
        return is_owner
    return commands.check(predicate)


def is_admin():
    async def pred(ctx):
        return await check_guild_permissions(ctx, {'administrator': True})
    return commands.check(pred)


def is_mod():
    async def pred(ctx):
        modrole = ctx.bot.settings.get_mod_role(ctx.guild.id)
        return has_role(ctx, modrole)
    return commands.check(pred)


def DJ_or(alone: bool=False, current: bool=False):
    async def predicate(ctx):
        try:
            player = ctx.bot.lavalink.players.get(ctx.guild.id)
            is_alone = (ctx.author in player.listeners and len(player.listeners) == 1) and alone

            requester = (player.current.requester == ctx.author.id) and current

            is_dj = has_role(ctx, 'DJ') or has_role(ctx, 'dj') or has_role(ctx, 'Dj')
            is_admin = await check_guild_permissions(ctx, {'administrator': True})

            return is_dj or is_admin or is_alone or requester
        except AttributeError:
            return False
    return commands.check(predicate)
