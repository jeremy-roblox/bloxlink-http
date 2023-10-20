from __future__ import annotations

import logging
import re
from typing import Any, Callable

import hikari

from resources.exceptions import *
from resources.models import CommandContext
from resources.response import Response
from resources.secrets import DISCORD_APPLICATION_ID  # pylint: disable=no-name-in-module

command_name_pattern = re.compile("(.+)Command")

slash_commands = {}


async def handle_command(interaction: hikari.CommandInteraction):
    """Handle a command interaction."""
    command_name = interaction.command_name
    command_type = interaction.command_type

    command = None
    subcommand_name: str = None
    command_options: dict = None

    # find command
    if command_type == hikari.CommandType.SLASH:
        command: Command = slash_commands.get(command_name)

        if not command:
            return

        # subcommand checking
        subcommand_option: list[hikari.CommandInteractionOption] = list(
            filter(lambda o: o.type == hikari.OptionType.SUB_COMMAND, interaction.options or [])
        )
        subcommand_name = subcommand_option[0].name if subcommand_option else None

    else:
        raise NotImplementedError()

    # get options
    if interaction.options:
        for option in interaction.options:
            if option.name == subcommand_name:
                command_options = {o.name: o.value for o in option.options}
                break
        else:
            command_options = {o.name: o.value for o in interaction.options}

    response = Response(interaction)

    if command.defer:
        response.responded = True
        yield interaction.build_deferred_response()

    ctx = CommandContext(
        command_name=interaction.command_name,
        command_id=interaction.command_id,
        guild_id=interaction.guild_id,
        member=interaction.member,
        user=interaction.user,
        response=response,
        resolved=interaction.resolved,
        options=command_options,
        interaction=interaction,
    )

    await try_command(command.execute(ctx, subcommand_name=subcommand_name), response)


async def handle_autocomplete(interaction: hikari.AutocompleteInteraction):
    """Handle an autocomplete interaction."""
    # Iterate through commands and find the autocomplete function that corresponds to the slash cmd option name.
    for command in slash_commands.values():
        if not command.autocomplete_handlers:
            continue

        if not command.name == interaction.command_name:
            continue

        for command_option in interaction.options:
            if not command_option.is_focused:
                continue

            autocomplete_fn = command.autocomplete_handlers.get(command_option.name)

            if not autocomplete_fn:
                logging.error(f'Command {command.name} has no auto-complete handler "{command_option.name}"!')
                return

            return await autocomplete_fn(interaction)


async def handle_component(interaction: hikari.ComponentInteraction):
    """Handle a component interaction."""
    custom_id = interaction.custom_id

    # iterate through commands and find the custom_id mapped function
    for command in slash_commands.values():
        for accepted_custom_id, custom_id_fn in command.accepted_custom_ids.items():
            if custom_id.startswith(accepted_custom_id):
                return await custom_id_fn(interaction)


def new_command(command: Any, **kwargs):
    """Registers a command with Bloxlink.

    This is only used for the wrapper function in resources.bloxlink on the bot object. Commands should not
    be added using this method directly.

    Args:
        command (Any): The command to register locally. (Presumably callable)
    """
    new_command_class = command()

    command_name = command_name_pattern.search(command.__name__).group(1).lower()
    command_fn = getattr(new_command_class, "__main__", None)  # None if it has sub commands
    subcommands: dict[str, Callable] = {}
    rest_subcommands: list[hikari.CommandOption] = []

    for attr_name in dir(new_command_class):
        attr = getattr(new_command_class, attr_name)

        if hasattr(attr, "__issubcommand__"):
            rest_subcommands.append(
                hikari.CommandOption(
                    type=hikari.OptionType.SUB_COMMAND,
                    name=attr.__name__,
                    description=attr.__doc__,
                    options=attr.__subcommandattrs__.get("options"),
                )
            )
            subcommands[attr_name] = attr

    command_attrs = {
        "name": command_name,
        "fn": command_fn,
        "category": kwargs.get("category", "Miscellaneous"),
        "permissions": kwargs.get("permissions", None),
        "defer": kwargs.get("defer", False),
        "description": new_command_class.__doc__,
        "options": kwargs.get("options"),
        "subcommands": subcommands,
        "rest_subcommands": rest_subcommands,
        "accepted_custom_ids": kwargs.get("accepted_custom_ids"),
        "autocomplete_handlers": kwargs.get("autocomplete_handlers"),
        "dm_enabled": kwargs.get("dm_enabled"),
    }

    new_command = Command(**command_attrs)
    slash_commands[command_name] = new_command

    for alias in kwargs.get("aliases", []):
        command_attrs["name"] = alias
        new_alias_command = Command(**command_attrs)
        slash_commands[alias] = new_alias_command
        logging.info(f"Registered command alias {alias} of {command_name}")

    logging.info(f"Registered command {command_name}")


async def sync_commands(bot: hikari.RESTBot):
    """Publish our slash commands to Discord.

    Args:
        bot (hikari.RESTBot): The bot object to publish slash commands for.
    """
    commands = []

    for new_command_data in slash_commands.values():
        command: hikari.commands.SlashCommandBuilder = bot.rest.slash_command_builder(
            new_command_data.name, new_command_data.description
        )

        if new_command_data.rest_subcommands:
            for sucommand in new_command_data.rest_subcommands:
                command.add_option(sucommand)

        if new_command_data.permissions:
            command.set_default_member_permissions(new_command_data.permissions)

        if new_command_data.options:
            for option in new_command_data.options:
                command.add_option(option)

        if new_command_data.dm_enabled is not None:
            command.set_is_dm_enabled(new_command_data.dm_enabled)

        commands.append(command)

    await bot.rest.set_application_commands(
        application=DISCORD_APPLICATION_ID,
        commands=commands,
    )

    logging.info(f"Registered {len(slash_commands)} slash commands.")


async def try_command(fn: Callable, response: Response):
    """Run a command with top-level exception handling.

    Top level exceptions include default messages for custom exceptions that are defined in
    resources.exceptions.

    Caught exceptions currently consist of:
        - UserNotVerified
        - BloxlinkForbidden
        - hikari.errors.ForbiddenError
        - RobloxNotFound
        - RobloxDown
        - Message

    Args:
        fn (Callable): Command function that is being triggered,
        response (Response): Response object for the interaction that triggered the command.
    """
    try:
        await fn
    except UserNotVerified as message:
        await response.send(str(message) or "This user is not verified with Bloxlink!")
    except (BloxlinkForbidden, hikari.errors.ForbiddenError) as message:
        await response.send(
            str(message)
            or "I have encountered a permission error! Please make sure I have the appropriate permissions."
        )
    except RobloxNotFound as message:
        await response.send(
            str(message) or "This Roblox entity does not exist! Please check the ID and try again."
        )
    except RobloxDown:
        await response.send(
            "Roblox appears to be down, so I was unable to process your command. "
            "Please try again in a few minutes."
        )
    except Message as ex:
        await response.send(ex.message)


class Command:
    """Base representation of a slash command on Discord"""

    def __init__(
        self,
        name: str,
        fn: Callable = None,  # None if it has sub commands
        category: str = "Miscellaneous",
        permissions=None,
        defer: bool = False,
        description: str = None,
        options: list[hikari.commands.CommandOptions] = None,
        subcommands: dict[str, Callable] = None,
        rest_subcommands: list[hikari.CommandOption] = None,
        accepted_custom_ids: list[str] = None,
        autocomplete_handlers: list[str] = None,
        dm_enabled: bool = None,
    ):
        self.name = name
        self.fn = fn
        self.category = category
        self.permissions = permissions
        self.defer = defer
        self.description = description
        self.options = options
        self.subcommands = subcommands
        self.rest_subcommands = rest_subcommands
        self.accepted_custom_ids = accepted_custom_ids or {}
        self.autocomplete_handlers = autocomplete_handlers or {}
        self.dm_enabled = dm_enabled

    async def execute(self, ctx: CommandContext, subcommand_name: str = None):
        """Execute a command (or its subcommand)

        Args:
            ctx (CommandContext): Context for this command.
            subcommand_name (str, optional): Name of the subcommand to trigger. Defaults to None.
        """
        # TODO: check for permissions

        if subcommand_name:
            await self.subcommands[subcommand_name](ctx)
        else:
            await self.fn(ctx)
