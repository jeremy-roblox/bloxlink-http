import hikari
from resources.bloxlink import instance as bloxlink

async def get_component(message: hikari.Message, custom_id: str):
    for action_row in message.components:
        for component in action_row.components:
            if component.custom_id.startswith(custom_id):
                return component


async def save_components(message: hikari.Message, values: list = None):
    """Hikari requires a new builder for component edits"""

    components = []

    for action_row in message.components:
        for component in action_row.components:
            if isinstance(component, hikari.SelectMenuComponent):
                new_select_menu = (
                    bloxlink.rest.build_action_row().add_select_menu(component.custom_id)
                        .set_placeholder(component.placeholder))

                for option in component.options:
                    new_select_menu = new_select_menu.add_option(option.label, option.value).set_is_default(option.value in values).add_to_menu()

                new_select_menu = new_select_menu.add_to_container()

                components.append(new_select_menu)

    await message.edit(components=components)

async def get_custom_id_segment():
    pass

async def set_custom_id_data(message: hikari.Message, custom_id: str, segment: int, values: list):
    component = await get_component(message, custom_id=custom_id)

    if component:
        custom_id_data = component.custom_id.split(":")

        if len(custom_id_data) < segment:
            for _ in range(segment-len(custom_id_data)):
                custom_id_data.append("")

            custom_id = ":".join(custom_id_data)

        segment_data = (custom_id_data[segment-1] if len(custom_id_data) >= segment else "").split(",")

        if segment_data[0] == "":
            # fix blank lists
            segment_data.pop(0)

        for value in values:
            value = value.strip()
            if value not in segment_data:
                segment_data.append(value)

        custom_id_data[segment-1] = ",".join(segment_data)
        component.custom_id = ":".join(custom_id_data)

        await save_components(message, values)

async def check_all_modified(message: hikari.Message, *custom_ids: tuple[str]) -> bool:
    for action_row in message.components:
        for component in action_row.components:
            for custom_id in custom_ids:
                if component.custom_id == custom_id:
                    return False

    return True