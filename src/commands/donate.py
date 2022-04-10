from attr import field
from snowfin import Module, slash_command, Embed, Interaction, EmbedField, Button, Components, EmbedFooter
from resources.bloxlink import Bloxlink
from resources.constants import LIMITS

PREMIUM_PERKS = "\n".join([
    f"- More role bindings allowed (from {LIMITS['BINDS']['FREE']} to {LIMITS['BINDS']['PREMIUM']}).",
    f"- `persistRoles:` update users as they type once every 2 hours",
    f"- Access to the `Pro` version of Bloxlink - a bot in less servers, so downtime is very minimal.",
     "- Set an age limit that checks the person's Roblox account age. (`{prefix}settings change agelimit`).",
     "- Customize the name of Magic Roles (`{prefix}magicroles`).",
     "- No cooldown on some commands.",
     "- More restrictions (`{prefix}restrict`) " + f"allowed (from {LIMITS['RESTRICTIONS']['FREE']} to {LIMITS['RESTRICTIONS']['PREMIUM']}).",
     "- More groups allowed to be added to your Group-Lock (`{prefix}grouplock`).",
     "- And more! Check `{prefix}settings change` to view the premium settings."
])


class DonateCommand(Module):

    @slash_command("donate")
    async def donate(self, ctx: Interaction):
        """learn how to receive Bloxlink Premium"""

        embed = Embed(
            title="Bloxlink Premium",
            description="We appreciate all donations!\nBy donating a certain amount, you will receive **[Bloxlink Premium](https://www.patreon.com/join/bloxlink?)** " \
                        f"on __every server you own__ and receive these perks:\n{PREMIUM_PERKS.format(prefix='/')}",
            fields=[
                EmbedField(
                    name="Frequently Asked Questions",

                    value="1.) Can I transfer premium to someone else?\n" 
                          f"> Yes, use the `/transfer to` command. "
                          "You'll be able to disable the transfer whenever you want "
                          f"with `/transfer disable`.\n"
                          "2.) How do I receive my perks after donating?\n"
                          "> Link your Discord account to Patreon. After, wait 15-20 "
                          "minutes and your perks should be activated. Feel free to ask "
                          "in our support server if you need more help: <https://blox.link/support>."
                ),
            ],
            footer=EmbedFooter(text="Powered by Bloxlink", icon_url=self.client.user.avatar_url),
            color=0xdb2323
        )

        return embed, Button("Click to Subscribe ($6)", url="https://www.patreon.com/join/bloxlink?")
           
