import hikari
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.response import Prompt, PromptPageData, Response
from resources.components import Button, TextSelectMenu, TextInput
from resources.modals import build_modal





class SetupPrompt(Prompt):
    def __init__(self, interaction: hikari.CommandInteraction, response: Response):
        super().__init__(
            interaction,
            response,
            self.__class__.__name__
        )

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Thank you for choosing Bloxlink, the most popular Roblox-Discord integration! In a few simple prompts, we'll configure Bloxlink for your server."
                         ""
            ),
            components=[
                Button(
                    label="Next",
                    component_id="next",
                    is_disabled=False,
                ),
                Button(
                    label="Cancel",
                    component_id="cancel",
                    is_disabled=False,
                    style=Button.ButtonStyle.SECONDARY
                ),
            ]
        )
    )
    async def intro_page(self, interaction: hikari.CommandInteraction | hikari.ComponentInteraction, fired_component_id: str | None):
        match fired_component_id:
            case "next":
                return await self.next()
            case "cancel":
                return await self.finish()

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Should your members be given a different nickname? Please note that by default, Bloxlink will name users as: `Display Name (@Roblox Username)`.\n\n"
                         "You can select a preset template, or choose your own nickname format. You can even set a prefix (text before the nickname) and/or a suffix (text after the nickname)."
            ),
            components=[
                TextSelectMenu(
                    placeholder="Select a nickname preset...",
                    min_values=0,
                    max_values=1,
                    component_id="preset_nickname_select",
                    options=[
                        TextSelectMenu.Option(
                            label="Name users as: Roblox Display Name (@Roblox Username)",
                            value="{smart-name}",
                        ),
                        TextSelectMenu.Option(
                            label="Name users as: Roblox Username",
                            value="{roblox-name}",
                        ),
                        TextSelectMenu.Option(
                            label="Name users as: Roblox Display Name",
                            value="{display-name}",
                        ),
                        TextSelectMenu.Option(
                            label="Name users as: Discord Username",
                            value="{discord-name}",
                        ),
                        TextSelectMenu.Option(
                            label="Do not nickname users",
                            value="{disable-nicknaming}",
                        ),
                        TextSelectMenu.Option(
                            label="Choose my own nickname format...",
                            value="custom",
                        ),
                    ],
                ),
                Button(
                    label="Add a nickname prefix or suffix (optional)",
                    component_id="nickname_prefix_suffix",
                    is_disabled=False,
                ),
                Button(
                    label="Skip, leave unchanged",
                    component_id="skip",
                    is_disabled=False,
                    style=Button.ButtonStyle.SECONDARY
                ),
                Button(
                    label="Submit",
                    component_id="submit",
                    is_disabled=True,
                    style=Button.ButtonStyle.SUCCESS
                )
            ],
        )
    )
    async def nickname_page(self, interaction: hikari.ComponentInteraction | hikari.ModalInteraction, fired_component_id: str):
        existing_nickname_template = (await bloxlink.fetch_guild_data(self.guild_id, "nicknameTemplate")).nicknameTemplate

        match fired_component_id:
            case "preset_nickname_select":
                nickname = (await self.current_data(key_name="preset_nickname_select")).get("values")[0]

                if nickname == "custom":
                    modal = build_modal(
                        title="Add a Custom Nickname",
                        command_name=self.command_name,
                        interaction=interaction,
                        prompt_data = {
                            "page_number": self.current_page_number,
                            "prompt_name": self.__class__.__name__,
                            "component_id": fired_component_id
                        },
                        components=[
                            TextInput(
                                style=TextInput.TextInputStyle.SHORT,
                                placeholder="{smart-name}",
                                custom_id="nickname_prefix_input",
                                value="Type your nickname template...",
                                required=True
                            ),
                        ]
                    )

                    yield await self.response.send_modal(modal)

                    if not await modal.submitted():
                        return

                    yield await self.response.send_first(await modal.get_data())

                yield await self.response.send_first(
                    f"Updated the nickname template to {nickname}!\n"
                    "You may also add a nickname prefix and/or suffix.\n"
                    "After, press the **Submit** button to continue to the next page.",
                    ephemeral=True
                )

                await self.edit_page(
                    components={
                        "submit": {
                            "is_disabled": False,
                        },
                    }
                )

            case "nickname_prefix_suffix":
                modal = build_modal(
                    title="Add a Nickname Prefix and/or Suffix",
                    command_name=self.command_name,
                    interaction=interaction,
                    prompt_data = {
                        "page_number": self.current_page_number,
                        "prompt_name": self.__class__.__name__,
                        "component_id": fired_component_id
                    },
                    components=[
                        TextInput(
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="Type your nickname prefix...",
                            custom_id="nickname_prefix_input",
                            value="This will be shown FIRST in the nickname",
                            required=False
                        ),
                        TextInput(
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="Type your nickname suffix...",
                            custom_id="nickname_suffix_input",
                            value="This will be shown LAST in the nickname",
                            required=False
                        ),
                    ]
                )

                yield await self.response.send_modal(modal)

                if not await modal.submitted():
                    return

                modal_data = await modal.get_data()
                nickname_prefix = modal_data.get("nickname_prefix_input") or ""
                nickname_suffix = modal_data.get("nickname_suffix_input") or ""
                new_nickname_template = f"{nickname_prefix}{existing_nickname_template}{nickname_suffix}"

                yield await self.response.send_first(
                    "Added the nickname prefix and/or suffix!\n\n"
                    f"Prefix: {nickname_prefix}\n"
                    f"Suffix: {nickname_suffix}\n"
                    f"New template: {new_nickname_template}",
                    ephemeral=True
                )

            case "skip" | "submit":
                yield await self.next()

    @Prompt.programmatic_page()
    async def verified_role_page(self, interaction: hikari.ComponentInteraction | hikari.ModalInteraction, fired_component_id: str):

        yield PromptPageData(
            title="Setup Bloxlink",
            description=(
                "Do you want to change the name of your **Verified role**? "
                "This is the role that Bloxlink will give to users when they verify.\n\n"
            ),
            components=[
                Button(
                    label="Leave as default",
                    component_id="nickname_prefix_suffix",
                    is_disabled=False,
                ),
                Button(
                    label="Submit",
                    component_id="submit",
                    is_disabled=True,
                    style=Button.ButtonStyle.SUCCESS
                )
            ],
        )
        existing_nickname_template = (await bloxlink.fetch_guild_data(self.guild_id, "nicknameTemplate")).nicknameTemplate

        match fired_component_id:
            case "preset_nickname_select":
                nickname = (await self.current_data(key_name="preset_nickname_select")).get("values")[0]

                if nickname == "custom":
                    modal = build_modal(
                        title="Add a Custom Nickname",
                        command_name=self.command_name,
                        interaction=interaction,
                        prompt_data = {
                            "page_number": self.current_page_number,
                            "prompt_name": self.__class__.__name__,
                            "component_id": fired_component_id
                        },
                        components=[
                            TextInput(
                                style=TextInput.TextInputStyle.SHORT,
                                placeholder="{smart-name}",
                                custom_id="nickname_prefix_input",
                                value="Type your nickname template...",
                                required=True
                            ),
                        ]
                    )

                    yield await self.response.send_modal(modal)

                    if not await modal.submitted():
                        return

                    yield await self.response.send_first(await modal.get_data())

                yield await self.next()

            case "nickname_prefix_suffix":
                modal = build_modal(
                    title="Add a Nickname Prefix and/or Suffix",
                    command_name=self.command_name,
                    interaction=interaction,
                    prompt_data = {
                        "page_number": self.current_page_number,
                        "prompt_name": self.__class__.__name__,
                        "component_id": fired_component_id
                    },
                    components=[
                        TextInput(
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="Type your nickname prefix...",
                            custom_id="nickname_prefix_input",
                            value="This will be shown FIRST in the nickname",
                            required=False
                        ),
                        TextInput(
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="Type your nickname suffix...",
                            custom_id="nickname_suffix_input",
                            value="This will be shown LAST in the nickname",
                            required=False
                        ),
                    ]
                )

                yield await self.response.send_modal(modal)

                if not await modal.submitted():
                    return

                modal_data = await modal.get_data()
                nickname_prefix = modal_data.get("nickname_prefix_input") or ""
                nickname_suffix = modal_data.get("nickname_suffix_input") or ""
                new_nickname_template = f"{nickname_prefix}{existing_nickname_template}{nickname_suffix}"

                yield await self.response.send_first(
                    "Added the nickname prefix and/or suffix!\n\n"
                    f"Prefix: {nickname_prefix}\n"
                    f"Suffix: {nickname_suffix}\n"
                    f"New template: {new_nickname_template}",
                    ephemeral=True
                )



@bloxlink.command(
    category="Administration",
    defer=True,
    defer_with_ephemeral=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    dm_enabled=False,
    prompts=[SetupPrompt],
)
class SetupCommand:
    """setup Bloxlink for your server"""

    async def __main__(self, ctx: CommandContext):
        return await ctx.response.prompt(SetupPrompt)
