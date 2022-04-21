from unicodedata import category
from snowfin import Module, slash_command, MessageResponse, Interaction, Button
from resources.bloxlink import Bloxlink

class VerifyCommand(Module):
    category = "Account"

    @slash_command("verify")
    async def verify(self, ctx: Interaction):
        """link your Roblox account to your Discord account and get your server roles"""

        return (
            "To verify with Bloxlink, click the link below",
            Button("Verify with Bloxlink", url="https://blox.link/dashboard/verifications/verify?page=username", emoji="🔗"),
            Button("Stuck? See a Tutorial", url="https://www.youtube.com/watch?v=0SH3n8rY9Fg&list=PLz7SOP-guESE1V6ywCCLc1IQWiLURSvBE&index=2", emoji="❔")
        )