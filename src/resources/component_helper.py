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
            # Keep action row components together.
            temp = []
            for component in action_row_or_component.components:
                temp.append(component)
            iterate_components.append(temp)

    for component in iterate_components:
        # print("component=", component)
        if hasattr(component, "build"):
            new_components.append(component)

        elif isinstance(component, list):
            """Components in a list = in an action row."""
            row = bloxlink.rest.build_message_action_row()
            for subcomponent in component:
                if isinstance(subcomponent, hikari.SelectMenuComponent):
                    new_select_menu = row.add_select_menu(
                        subcomponent.type,
                        subcomponent.custom_id,
                        placeholder=subcomponent.placeholder,
                        min_values=subcomponent.min_values,
                        max_values=subcomponent.max_values,
                        is_disabled=subcomponent.is_disabled,
                    )

                    if subcomponent.type == hikari.ComponentType.TEXT_SELECT_MENU:
                        for option in subcomponent.options:
                            new_select_menu = new_select_menu.add_option(
                                option.label,
                                option.value,
                                description=option.description,
                                emoji=option.emoji,
                                is_default=option.is_default,
                            )

                elif isinstance(subcomponent, hikari.ButtonComponent):
                    if subcomponent.style == hikari.ButtonStyle.LINK:
                        if not subcomponent.emoji:
                            row.add_link_button(
                                subcomponent.url,
                                label=subcomponent.label,
                                is_disabled=subcomponent.is_disabled,
                            )
                        else:
                            row.add_link_button(
                                subcomponent.url,
                                emoji=subcomponent.emoji,
                                is_disabled=subcomponent.is_disabled,
                            )
                    else:
                        if not subcomponent.emoji:
                            row.add_interactive_button(
                                subcomponent.style,
                                subcomponent.custom_id,
                                label=subcomponent.label,
                                is_disabled=subcomponent.is_disabled,
                            )
                        else:
                            row.add_interactive_button(
                                subcomponent.style,
                                subcomponent.custom_id,
                                emoji=subcomponent.emoji,
                                is_disabled=subcomponent.is_disabled,
                            )

            new_components.append(row)

        elif isinstance(component, hikari.SelectMenuComponent):
            new_select_menu = row.add_select_menu(
                subcomponent.type,
                subcomponent.custom_id,
                placeholder=subcomponent.placeholder,
                min_values=subcomponent.min_values,
                max_values=subcomponent.max_values,
                is_disabled=subcomponent.is_disabled,
            )

            if subcomponent.type == hikari.ComponentType.TEXT_SELECT_MENU:
                for option in subcomponent.options:
                    new_select_menu = new_select_menu.add_option(
                        option.label,
                        option.value,
                        description=option.description,
                        emoji=option.emoji,
                        is_default=option.is_default,
                    )

            new_components.append(new_select_menu)

        elif isinstance(component, hikari.ButtonComponent):
            row = bloxlink.rest.build_message_action_row()
            if component.style == hikari.ButtonStyle.LINK:
                if not component.emoji:
                    row.add_link_button(
                        component.url,
                        label=component.label,
                        is_disabled=component.is_disabled,
                    )
                else:
                    row.add_link_button(
                        component.url,
                        emoji=component.emoji,
                        is_disabled=component.is_disabled,
                    )
            else:
                if not component.emoji:
                    row.add_interactive_button(
                        component.style,
                        component.custom_id,
                        label=component.label,
                        is_disabled=component.is_disabled,
                    )
                else:
                    row.add_interactive_button(
                        component.style,
                        component.custom_id,
                        emoji=component.emoji,
                        is_disabled=component.is_disabled,
                    )

            new_components.append(row)

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
                # print(component.custom_id)
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


def component_author_validation(author_segment: int = 2, ephemeral: bool = True, defer: bool = True):
    """Handle same-author validation for components.
    Utilized to ensure that the author of the command is the only one who can press buttons.

    Args:
        author_segment (int): The segment (as preferred by get_custom_id_data) where the original author's ID
            will be located in. Defaults to 2.
        ephemeral (bool): Set if the response should be ephemeral or not. Default is true.
            A user mention will be included in the response if not ephemeral.
        defer (bool): Set if the response should be deferred by the handler. Default is true.
    """

    def func_wrapper(func):
        async def response_wrapper(interaction: hikari.ComponentInteraction):
            author_id = get_custom_id_data(interaction.custom_id, segment=author_segment)

            # Only accept input from the author of the command
            # Presumes that the original author ID is the second value in the custom_id.
            if str(interaction.member.id) != author_id:
                # Could just silently fail too... Can't defer before here or else the eph response
                # fails to show up.
                return (
                    interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
                    .set_content(
                        f"You {f'(<@{interaction.member.id}>) ' if not ephemeral else ''}"
                        "are not the person who ran this command!"
                    )
                    .set_flags(hikari.MessageFlag.EPHEMERAL if ephemeral else None)
                )
            else:
                if defer:
                    await interaction.create_initial_response(
                        hikari.ResponseType.DEFERRED_MESSAGE_UPDATE,
                        flags=hikari.MessageFlag.EPHEMERAL if ephemeral else None,
                    )

            # Trigger original method
            return await func(interaction)

        return response_wrapper

    return func_wrapper
