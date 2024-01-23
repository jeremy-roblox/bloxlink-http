import logging
import argparse
from os import environ as env, listdir
from datetime import timedelta

import hikari
import uvicorn

from resources.bloxlink import Bloxlink
from resources.secrets import ( # pylint: disable=no-name-in-module
    DISCORD_PUBLIC_KEY,
    DISCORD_TOKEN,
    SERVER_HOST,
    SERVER_PORT,
)

# Make sure bot is accessible from most modules. We load the bot first before loading most modules.
bot = Bloxlink(
    public_key=DISCORD_PUBLIC_KEY,
    token=DISCORD_TOKEN,
    token_type=hikari.TokenType.BOT,
    asgi_managed=False,
)

# Load a few modules
from resources.commands import handle_interaction, sync_commands
from resources.constants import MODULES, BOT_RELEASE
from resources.redis import redis
from web.webserver import webserver


# Initialize logging and argument parsing
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument(
    "-s", "--sync-commands",
    action="store_true",
    help="sync commands and bypass the cooldown",
    required=False,
    default=False)
parser.add_argument(
    "-c", "--clear-redis",
    action="store_true",
    help="local only, clears redis",
    required=False,
    default=False)
args = parser.parse_args()


# Initialize the web server
# IMPORTANT NOTE: blacksheep expects a trailing /
# in the URL that is given to discord because this is a mount.
# Example: "example.org/bot/" works, but "example.org/bot" does not (this results in a 307 reply, which discord doesn't honor).
webserver.mount("/bot", bot)

@webserver.on_start
async def handle_start(_):
    """Start the bot and sync commands"""

    await bot.start()

    # only sync commands once every hour unless the --sync-commands flag is passed
    if args.sync_commands or not await redis.get("synced_commands"):
        await redis.set("synced_commands", "true", ex=timedelta(hours=1).seconds)
        await sync_commands(bot)
    else:
        logger.info("Skipping command sync. Run with --sync-commands or -s to force sync.")

    if BOT_RELEASE == "LOCAL" and args.clear_redis:
        await redis.flushall()
        logger.info("Cleared redis. Run with --clear-redis or -c to force clear.")


@webserver.on_stop
async def handle_stop(_):
    """Executes when the bot is stopped"""

    await bot.close()


if __name__ == "__main__":
    # Register the interaction handler for all interaction types.
    for interaction_type in (hikari.CommandInteraction, hikari.ComponentInteraction, hikari.AutocompleteInteraction, hikari.ModalInteraction):
        bot.interaction_server.set_listener(interaction_type, handle_interaction)

    for directory in MODULES:
        files = [
            name
            for name in listdir("src/" + directory.replace(".", "/"))
            if name[:1] != "." and name[:2] != "__" and name != "_DS_Store"
        ]

        for filename in [f.replace(".py", "") for f in files]:
            if filename in ("bot", "__init__"):
                continue

            bot.load_module(f"{directory.replace('/','.')}.{filename}")

    uvicorn.run(
        webserver,
        host=env.get("HOST", SERVER_HOST),
        port=env.get("PORT", SERVER_PORT),
        log_config=None,
    )
