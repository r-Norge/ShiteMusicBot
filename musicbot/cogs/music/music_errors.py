# Discord Packages
from discord.ext.commands import CommandError

from typing import Optional


class MusicError(CommandError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        self.inner_error = inner_error
        super().__init__(message)


class PlayerNotAvailableError(MusicError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


class MissingPermissionsError(MusicError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


class BotNotConnectedError(MusicError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


class UserNotConnectedError(MusicError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


class PlayBackStatusError(MusicError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


class RequirePlayingError(PlayBackStatusError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


class RequireListeningError(PlayBackStatusError):
    def __init__(self, message: str, inner_error: Optional[Exception] = None):
        super().__init__(message, inner_error=inner_error)


# Channel errors
class ChannelError(MusicError):
    def __init__(self, message: str, channels, inner_error: Optional[Exception] = None):
        self.channels = channels
        super().__init__(message=message, inner_error=inner_error)


class VoiceChannelFullError(ChannelError):
    def __init__(self, message: str, channel, inner_error: Optional[Exception] = None):
        super().__init__(message, channels=[channel], inner_error=inner_error)


class UserInDifferentVoiceChannelError(ChannelError):
    def __init__(self, message: str, channel, inner_error: Optional[Exception] = None):
        super().__init__(message, channels=[channel], inner_error=inner_error)


class ConfiguredChannelsError(ChannelError):
    def __init__(self, message: str, channels, inner_error: Optional[Exception] = None):
        super().__init__(message, channels=channels, inner_error=inner_error)


class WrongVoiceChannelError(ConfiguredChannelsError):
    def __init__(self, message: str, channels, inner_error: Optional[Exception] = None):
        super().__init__(message, channels=channels, inner_error=inner_error)


class WrongTextChannelError(ConfiguredChannelsError):
    def __init__(self, message: str, channels, inner_error: Optional[Exception] = None):
        super().__init__(message, channels=channels, inner_error=inner_error)
