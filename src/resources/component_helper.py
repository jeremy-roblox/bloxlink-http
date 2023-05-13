import hikari
from resources.bloxlink import instance as bloxlink


async def get_component(message: hikari.Message, custom_id: str):
    for action_row in message.components:
        for component in action_row.components:
            if component.custom_id.startswith(custom_id):
                return component


async def set_components(message: hikari.Message, *, values: list = None, components: list = None):
    """Hikari requires a new builder for component edits"""

    new_components = []
    components = components or []
    values = values or []

    iterate_components = []

    for action_row_or_component in components or message.components:
        if hasattr(action_row_or_component, "build"):
            iterate_components.append(action_row_or_component)
        else:
            for component in action_row_or_component.components:
                iterate_components.append(component)

    for component in iterate_components:
        print("component=", component)
        if hasattr(component, "build"):
            new_components.append(component)

        elif isinstance(component, hikari.SelectMenuComponent):
            new_select_menu = (
                bloxlink.rest.build_message_action_row()
                .add_select_menu(component.custom_id)
                .set_placeholder(component.placeholder)
            )

            for option in component.options:
                new_select_menu = (
                    new_select_menu.add_option(option.label, option.value)
                    .set_is_default(option.value in values)
                    .add_to_menu()
                )

            new_select_menu = new_select_menu.add_to_container()

            new_components.append(new_select_menu)

        elif isinstance(component, hikari.ButtonComponent):
            print("new button component", component.custom_id)
            new_button_menu = (
                bloxlink.rest.build_message_action_row()
                .add_button(component.style, component.custom_id)
                .set_label(component.label)
            )

            new_button_menu = new_button_menu.add_to_container()

            new_components.append(new_button_menu)

    await message.edit(embeds=message.embeds, components=new_components)


def get_custom_id_data(
    custom_id: str,
    segment: int = None,
    segment_min: int = None,
    segment_max: int = None,
    message: hikari.Message = None,
) -> str | tuple | None:
    if message:
        for action_row in message.components:
            for component in action_row.components:
                print(component.custom_id)
                if component.custom_id.startswith(custom_id):
                    custom_id = component.custom_id

    if isinstance(custom_id, hikari.Snowflake):
        custom_id = str(custom_id)

    custom_id_data = custom_id.split(":")
    segment_data = None

    if segment:
        segment_data = custom_id_data[segment - 1] if len(custom_id_data) >= segment else None
    elif segment_min:
        segment_data = tuple(
            custom_id_data[segment_min - 1 : (segment_max if segment_max else len(custom_id_data))]
        )

    return segment_data


async def set_custom_id_data(message: hikari.Message, custom_id: str, segment: int, values: list | str):
    component = await get_component(message, custom_id=custom_id)

    if isinstance(values, str):
        values = [values]

    if component:
        custom_id_data = component.custom_id.split(":")

        if len(custom_id_data) < segment:
            for _ in range(segment - len(custom_id_data)):
                custom_id_data.append("")

            custom_id = ":".join(custom_id_data)

        segment_data = (custom_id_data[segment - 1] if len(custom_id_data) >= segment else "").split(",")

        if segment_data[0] == "":
            # fix blank lists
            segment_data.pop(0)

        for value in values:
            value = value.strip()
            if value not in segment_data:
                segment_data.append(value)

        custom_id_data[segment - 1] = ",".join(segment_data)
        component.custom_id = ":".join(custom_id_data)

        await set_components(message, values=values)


async def check_all_modified(message: hikari.Message, *custom_ids: tuple[str]) -> bool:
    for action_row in message.components:
        for component in action_row.components:
            if component.custom_id in custom_ids:
                return False

    return True
