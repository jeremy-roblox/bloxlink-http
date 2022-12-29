from os import environ as env, listdir
from resources.constants import MODULES
from config import SERVER_HOST, SERVER_PORT
from resources.secrets import DISCORD_PUBLIC_KEY, DISCORD_TOKEN
from resources.bloxlink import Bloxlink
from resources.commands import handle_command, sync_commands, handle_component
import logging
import hikari

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    bot = Bloxlink(
        public_key=DISCORD_PUBLIC_KEY,
        token=DISCORD_TOKEN,
        token_type=hikari.TokenType.BOT,
    )

    for directory in MODULES:
        files = [name for name in listdir('src/'+directory.replace('.', '/')) if name[:1] != "." and name[:2] != "__" and name != "_DS_Store"]

        for filename in [f.replace(".py", "") for f in files]:
            if filename in ('bot', '__init__'):
                continue

            bot.load_module(f"{directory.replace('/','.')}.{filename}")


    bot.set_listener(hikari.CommandInteraction, handle_command)
    bot.set_listener(hikari.ComponentInteraction, handle_component)
    bot.add_startup_callback(sync_commands)
    bot.run(host=env.get("HOST", SERVER_HOST), port=env.get("PORT", SERVER_PORT))
