from datetime import datetime
import hikari


def pagination_validation(timeout_mins: int = 15):
    """Handle generic logic for pagination, such as author validation and prompt timeouts.
    Automatically defers if the prompt isn't timed out or the interaction author doesn't match the original author.
    The original author is presumed to be the first element in the custom_id (index 1).
    """

    def func_wrapper(func):
        async def response_wrapper(interaction: hikari.ComponentInteraction):
            custom_id_data = interaction.custom_id.split(":")
            author_id = custom_id_data[1]

            # >= 15 minutes, tell the user to make a new prompt + remove buttons.
            time_diff = datetime.utcnow() - interaction.message.timestamp.replace(tzinfo=None)
            if (time_diff.seconds / 60) >= timeout_mins:
                await interaction.create_initial_response(
                    hikari.ResponseType.DEFERRED_MESSAGE_CREATE, flags=hikari.MessageFlag.EPHEMERAL
                )

                await interaction.edit_message(message=interaction.message, components=[])
                await interaction.edit_initial_response(
                    "This prompt is quite old, please run the command again and use that prompt instead."
                )
                # Return something so Hikari doesn't complain.
                return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)

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
