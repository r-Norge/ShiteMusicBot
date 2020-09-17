# define Python user-defined exceptions
# Discord Packages
from discord.ext.commands import CommandError


class WrongChannelError(CommandError):
    def __init__(self, e: str, channels=None):
        self.original = e
        self.channels = channels
        super().__init__()


class WrongVoiceChannelError(WrongChannelError):
    def __init__(self, e: str, channels=None):
        super().__init__(e, channels=channels)


class WrongTextChannelError(WrongChannelError):
    def __init__(self, e: str, channels=None):
        super().__init__(e, channels=channels)
