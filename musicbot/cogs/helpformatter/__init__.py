from .help import Help
from .helpformatter import commandhelper

__all__ = ['Help', 'commandhelper']


async def setup(bot):
    bot.remove_command("help")
    await bot.add_cog(Help(bot))
