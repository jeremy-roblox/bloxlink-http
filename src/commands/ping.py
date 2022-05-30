from unicodedata import category
from snowfin import Module, slash_command, MessageResponse, Interaction
from resources.bloxlink import Bloxlink

class PingCommand(Module):
    """A module that responds to ping commands"""

    category = "Miscellaneous"

    @slash_command("ping")
    async def ping(self, ctx: Interaction):
        """check if the bot is alive"""

        return MessageResponse(f"Pong!", ephemeral=True)
