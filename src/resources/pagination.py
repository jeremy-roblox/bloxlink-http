from datetime import datetime
from resources.component_helper import get_custom_id_data
import hikari


def pagination_validation(timeout_mins: int = 15):
    """Handle generic logic for pagination, such as author validation. Automatically defers.

    The original author is presumed to be the first element in the custom_id after the
    command name (in the case of viewbinds) - (index 1 raw, segment 2 for get_custom_id_data).
    """

    def func_wrapper(func):
        async def response_wrapper(interaction: hikari.ComponentInteraction):
            author_id = get_custom_id_data(interaction.custom_id, segment=2)

            # Only accept input from the author of the command
            # Presumes that the original author ID is the second value in the custom_id.
            if str(interaction.member.id) != author_id:
                # Could just silently fail too... Can't defer before here or else the eph response
                # fails to show up.
                return (
                    interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
                    .set_content("You are not the person who ran this command!")
                    .set_flags(hikari.MessageFlag.EPHEMERAL)
                )
            else:
                await interaction.create_initial_response(
                    hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, flags=hikari.MessageFlag.EPHEMERAL
                )

            # Trigger original method
            await func(interaction)

            return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)

        return response_wrapper

    return func_wrapper
