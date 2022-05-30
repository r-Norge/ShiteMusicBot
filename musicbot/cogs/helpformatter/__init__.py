from .help import Help
from .helpformatter import commandhelper

__all__ = ['Help', 'commandhelper']


def setup(bot):
    bot.remove_command("help")
    bot.add_cog(Help(bot))
