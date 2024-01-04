class BloxlinkException(Exception):
    def __init__(self, message=None, ephemeral=False):
        self.message = message
        self.ephemeral = ephemeral

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

class PromptException(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CancelPrompt(PromptException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PageNotFound(PromptException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CancelCommand(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BadArgument(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class CommandException(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class AlreadyResponded(CommandException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BindException(BloxlinkException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BindConflictError(BindException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
