from snowfin.response import MessageResponse
from resources.structures import Bloxlink, Command

@Bloxlink.command
class PingCommand(Command):

    def __init__(self):
        super().__init__(self)

        self.some_data = "oooooooof"

    async def __execute__(self, interaction):
        return MessageResponse("pong, data=" + self.some_data)
