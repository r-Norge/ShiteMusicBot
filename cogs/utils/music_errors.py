# define Python user-defined exceptions
# Discord Packages
from discord.ext.commands import CommandError


class WrongVoiceChannelError(CommandError):
    """Raised when a command requires the user to be in the correct voicechannel"""

    def __init__(self, e, channels=None):
        self.original = e
        self.channels = channels
        super().__init__('You need to be in the right voice channel')
