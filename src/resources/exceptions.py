
class RobloxNotFound(Exception):
    def __init__(self, message):
        self.message = message

class RobloxAPIError(Exception):
    def __init__(self, message):
        self.message = message

class RobloxDown(Exception):
    def __init__(self, message):
        self.message = message