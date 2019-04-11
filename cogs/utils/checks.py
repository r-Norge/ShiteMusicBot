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
            ctx.message.author.id == 142212883512557569 or ctx.message.author.id == 212635519706726410 or
            ctx.message.author.id == 170506717140877312)
        return is_owner
    return commands.check(predicate)


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


def is_DJ(ctx):
    dj_role_ids = ctx.bot.settings.get(ctx.guild, 'roles.dj', [])
    if not dj_role_ids:
        return any([has_role(ctx, role) for role in ['dj', 'Dj', 'DJ', 'dJ']])
    else:
        return any([has_role_id(ctx, role_id) for role_id in dj_role_ids])


def DJ_or(alone: bool=False, current: bool=False):
    async def predicate(ctx):
        try:
            player = ctx.bot.lavalink.players.get(ctx.guild.id)
            is_alone = (ctx.author in player.listeners and len(player.listeners) == 1) and alone
            requester = (player.current.requester == ctx.author.id) and current

        except AttributeError:
            requester = False
            is_alone = False

        is_dj = is_DJ(ctx)

        return is_dj or is_alone or requester
    return commands.check(predicate)
