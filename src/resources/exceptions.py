from typing import Callable
from .response import Response


class BloxlinkException(Exception):
    def __init__(self, message=None):
        self.message = message

class RobloxNotFound(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class RobloxAPIError(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class RobloxDown(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class UserNotVerified(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Message(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BloxlinkForbidden(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CancelPrompt(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CancelCommand(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class BadArgument(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


async def try_command(fn: Callable, response: Response):
    try:
        await fn
    except UserNotVerified as message:
        await response.send(str(message) or "This user is not verified with Bloxlink!")
