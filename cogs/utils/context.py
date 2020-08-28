# Discord Packages
from discord.ext import commands


class Context(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.message.guild:
            self.locale = self.bot.settings.get(self.message.guild, 'locale', 'default_locale')
        else:
            self.locale = self.bot.settings.default_locale
