from attrs import define, field, fields
import hikari
import json
from resources.components import Component, get_custom_id, BaseCustomID
from resources.redis import redis
import resources.response as response

@define(slots=True, kw_only=True)
class ModalCustomID(BaseCustomID):
    """Represents a custom ID for a modal component."""

    component_custom_id: str = field(default="")


@define
class Modal:
    """Represents a Discord Modal."""

    builder: hikari.impl.InteractionModalBuilder | None
    custom_id: str
    data: dict = None
    command_options: dict = None

    async def submitted(self):
        """Returns whether the modal was submitted."""

        if self.data is None:
            await self.get_data()

        return self.data is not None

    async def get_data(self, *keys: tuple[str]):
        """Returns the data from the modal."""

        modal_data = {}

        if self.data is not None:
            modal_data = self.data
        else:
            modal_data = await redis.get(f"modal_data:{self.custom_id}")

            if modal_data is None:
                return None

            modal_data = json.loads(modal_data) if modal_data else {}

        self.data = modal_data

        if keys:
            if len(keys) == 1:
                return modal_data.get(keys[0])

            return {key: modal_data.get(key) for key in keys}

        return self.data

    async def clear_data(self):
        """Clears the data from the modal."""

        await redis.delete(f"modal_data:{self.custom_id}")
        self.data = None


def build_modal(title: str, components: list[Component], *, interaction: hikari.ComponentInteraction | hikari.CommandInteraction, command_name: str, prompt_data: dict = None, command_data: dict = None) -> Modal:
    """Build a modal response. This needs to be separately returned."""

    prompt_data = prompt_data or {}
    command_data = command_data or {}

    if command_data:
        new_custom_id = get_custom_id(
            ModalCustomID,
            command_name=command_name,
            subcommand_name=command_data.get("subcommand_name") or "",
            user_id=interaction.user.id,
            component_custom_id=prompt_data.get("component_id") or "",
        )
    elif prompt_data:
        new_custom_id = get_custom_id(
            response.PromptCustomID,
            command_name=command_name,
            subcommand_name=command_data.get("subcommand_name") or "",
            prompt_name=prompt_data.get("prompt_name") or "",
            user_id=interaction.user.id,
            page_number=prompt_data.get("page_number") or 0,
            prompt_message_id=prompt_data.get("prompt_message_id") or 0,
            component_custom_id=prompt_data.get("component_id") or "",
        )
    else:
        raise ValueError("Either prompt_data or command_data must be provided.")

    modal_builder: hikari.impl.InteractionModalBuilder = None

    if not isinstance(interaction, hikari.ModalInteraction):
        modal_builder = interaction.build_modal_response(title, str(new_custom_id))
        modal_action_row = hikari.impl.ModalActionRowBuilder()

        for component in components:
            modal_action_row = hikari.impl.ModalActionRowBuilder()

            modal_action_row.add_text_input(
                component.custom_id,
                component.value,
                placeholder=component.placeholder or "Enter a value...",
                min_length=component.min_length or 1,
                max_length=component.max_length or 2000,
                required=component.required or False,
                style=component.style or hikari.TextInputStyle.SHORT,
            )

            modal_builder.add_component(modal_action_row)

    return Modal(
        builder=modal_builder,
        custom_id=new_custom_id,
        command_options=command_data.get("options")
    )