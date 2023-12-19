from attrs import define, field, fields
import hikari
import json
from resources.components import Component, get_custom_id
from resources.redis import redis

@define
class ModalCustomID:
    """Represents a custom ID for a modal component."""

    command_name: str
    prompt_name: str
    user_id: int = field(converter=int)
    page_number: int = field(converter=int)
    component_custom_id: str

    def __str__(self):
        field_values = [str(getattr(self, field.name)) for field in fields(self.__class__)]
        return ":".join(field_values)


@define
class Modal:
    """Represents a Discord Modal."""

    builder: hikari.impl.InteractionModalBuilder | None
    custom_id: str
    data: dict = None

    async def submitted(self):
        """Returns whether the modal was submitted."""

        if self.data is None:
            await self.get_data()

        return self.data is not None

    async def get_data(self):
        """Returns the data from the modal."""

        if self.data is not None:
            return self.data

        modal_data = await redis.get(f"modal_data:{self.custom_id}")
        self.data = json.loads(modal_data) if modal_data else None

        return self.data


def build_modal(title: str, components: list[Component], *, interaction: hikari.ComponentInteraction, command_name: str, prompt_data: dict = None):
    """Build a modal response. This needs to be separately returned."""

    new_custom_id = get_custom_id(
        ModalCustomID,
        command_name=command_name,
        prompt_name=prompt_data["prompt_name"] or "",
        user_id=interaction.user.id,
        page_number=prompt_data["page_number"],
        component_custom_id=prompt_data["component_id"],
    )

    modal_builder: hikari.impl.InteractionModalBuilder = None

    if not isinstance(interaction, hikari.ModalInteraction):
        modal_builder = interaction.build_modal_response(title, str(new_custom_id))
        modal_action_row = hikari.impl.ModalActionRowBuilder()

        for component in components:
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
    )