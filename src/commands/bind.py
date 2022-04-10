from snowfin import Module, slash_command, MessageResponse, Interaction
from resources.bloxlink import Bloxlink

class BindCommand(Module):

    @slash_command("bind")
    async def bind(self, ctx: Interaction):
        """bind a discord role to a roblox group, asset, or badge"""

        return MessageResponse("change this from the dashboard", ephemeral=True)
