class Command:
    def __init__(self, command_obj):
        self.command_name = command_obj.__class__.__name__.strip("Command").lower()

    def __str__(self):
        return self.command_name
