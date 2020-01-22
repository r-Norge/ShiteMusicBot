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


def is_admin():
    async def pred(ctx):
        return await check_guild_permissions(ctx, {'administrator': True})
    return commands.check(pred)


def is_mod():
    async def pred(ctx):
        modrole = ctx.bot.settings.get(ctx.guild, 'roles.moderator', 'default_mod')
        return has_role(ctx, modrole)
    return commands.check(pred)


def has_role_id(ctx, role_id):
    if ctx.channel is discord.DMChannel:
        return False

    role = discord.utils.get(ctx.author.roles, id=role_id)
    return role is not None


def is_dj(ctx):
    dj_role_ids = ctx.bot.settings.get(ctx.guild, 'roles.dj', [])
    if not dj_role_ids:
        return any([has_role(ctx, role) for role in ['dj', 'Dj', 'DJ', 'dJ']])
    else:
        return any([has_role_id(ctx, role_id) for role_id in dj_role_ids])


def dj_or(alone: bool = False, track_requester: bool = False):
    async def predicate(ctx):
        try:
            player = ctx.bot.lavalink.players.get(ctx.guild.id)
            is_alone = (ctx.author in player.listeners and len(player.listeners) == 1) and alone
            requester = (player.current.requester == ctx.author.id) and track_requester

        except AttributeError:
            requester = False
            is_alone = False

        dj = is_dj(ctx)

        return dj or is_alone or requester
    return commands.check(predicate)
