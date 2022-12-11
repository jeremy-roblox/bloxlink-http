from __future__ import annotations
import re
import logging
import hikari
from .models import CommandContext
from .response import Response
from .exceptions import try_command
from config import DISCORD_APPLICATION_ID
from typing import Any, Callable


command_name_pattern = re.compile("(.+)Command")

slash_commands = {}


async def handle_command(interaction:hikari.CommandInteraction):
    #print(dir(interaction))

    command_name = interaction.command_name
    command_type = interaction.command_type

    command = None

    if command_type == hikari.CommandType.SLASH:
        command: Command = slash_commands.get(command_name)

        if not command:
            return
    else:
        raise NotImplementedError()

    response = Response(interaction)

    if command.defer:
        await response.defer()

    ctx = CommandContext(
        command_name=interaction.command_name,
        command_id=interaction.command_id,
        guild_id=interaction.guild_id,
        member=interaction.member,
        user=interaction.user,
        response=response,
        resolved=interaction.resolved
    )

    print(ctx)

    await try_command(command.execute(ctx), response)

    return interaction.build_response() # basically don't respond to the webhook

def new_command(command: Any, **kwargs):
    new_command_class = command()

    command_name = command_name_pattern.search(command.__name__).group(1).lower()
    command_fn = getattr(new_command_class, "__main__")

    new_command = Command(command_name,
                          command_fn,
                          kwargs.get("category", "Miscellaneous"),
                          kwargs.get("permissions", None),
                          kwargs.get("defer", False),
                          new_command_class.__doc__,
                          kwargs.get("options"))

    slash_commands[command_name] = new_command

    logging.info(f"Registered command {command_name}")


async def sync_commands(bot: hikari.RESTBot):
    from resources.bloxlink import instance as bloxlink

    commands = []

    for new_command_data in slash_commands.values():
        command: hikari.commands.SlashCommandBuilder = bloxlink.rest.slash_command_builder(
            new_command_data.name, new_command_data.description)

        if new_command_data.options:
            for option in new_command_data.options:
                command.add_option(option)

        commands.append(command)


    await bloxlink.rest.set_application_commands(
        application=DISCORD_APPLICATION_ID,
        commands=commands,
    )

    logging.info(f"Registered {len(slash_commands)} slash commands.")



class Command:
    def __init__(
            self,
            command_name: str,
            fn: Callable,
            category: str="Miscellaneous",
            permissions=None,
            defer: bool=False,
            description: str=None,
            options: list[hikari.commands.CommandOptions]=None
        ):
        self.name = command_name
        self.fn = fn
        self.category = category
        self.permissions = permissions
        self.defer = defer
        self.description = description
        self.options = options

    async def execute(self, ctx: CommandContext):
        # TODO: check for permissions

        await self.fn(ctx)
