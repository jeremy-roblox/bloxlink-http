from os import environ as env, listdir
from resources.constants import MODULES
from config import SERVER_HOST, SERVER_PORT
from resources.secrets import DISCORD_PUBLIC_KEY, DISCORD_TOKEN
from resources.bloxlink import Bloxlink
from resources.webserver import instance as webserver
from resources.commands import handle_command, sync_commands, handle_component, handle_autocomplete
import logging
import hikari
import uvicorn


logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)

bot = Bloxlink(
    public_key=DISCORD_PUBLIC_KEY,
    token=DISCORD_TOKEN,
    token_type=hikari.TokenType.BOT,
    asgi_managed=False,
)
bot.interaction_server.set_listener(hikari.CommandInteraction, handle_command)
bot.interaction_server.set_listener(hikari.ComponentInteraction, handle_component)
bot.interaction_server.set_listener(hikari.AutocompleteInteraction, handle_autocomplete)

# IMPORTANT NOTE, blacksheep expects a trailing /
# in the URL that is given to discord because this is a mount.
# Example: "example.org/bot/" works, but "example.org/bot" does not (this results in a 307 reply, which discord doesn't honor).
webserver.mount("/bot", bot)


@webserver.on_start
async def handle_start(_):
    await bot.start()
    await sync_commands(bot)


@webserver.on_stop
async def handle_stop(_):
    await bot.close()


if __name__ == "__main__":
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
