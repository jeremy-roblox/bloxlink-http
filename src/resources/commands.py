import re
import logging
import hikari
from .models import CommandContext
from .response import Response



command_name_pattern = re.compile("(.+)Command")

slash_commands = {}


async def handle_command(interaction:hikari.CommandInteraction):
    print(dir(interaction))

    command_name = interaction.command_name
    command_type = interaction.command_type

    command = None

    if command_type == hikari.CommandType.SLASH:
        command = slash_commands.get(command_name)

        if not command:
            return
    else:
        raise NotImplementedError()

    ctx = CommandContext(
        command_name=interaction.command_name,
        command_id=interaction.command_id,
        guild_id=interaction.guild_id,
        member=interaction.member,
        response=Response(interaction)
    )

    print(ctx)

    await command(ctx)






    return interaction.build_response()


def new_command(command):
    new_command = command()

    command_name = command_name_pattern.search(command.__name__).group(1).lower()
    command_fn = getattr(new_command, "__main__")

    slash_commands[command_name] = command_fn

    logging.info(f"Registered command {command_name}")


