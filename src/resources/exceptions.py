
class BloxlinkException(Exception):
    def __init__(self, message):
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
