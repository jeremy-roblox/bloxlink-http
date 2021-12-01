from os import environ as env
from resources.constants import SERVER_HOST, SERVER_PORT, MODULE_DIR
from resources.secrets import DISCORD_PUBLIC_KEY
from resources.structures import Bloxlink
import asyncio

loop = asyncio.get_event_loop()


def load_modules():
    get_files = Bloxlink.get_module("utils", attrs="get_files")

    for directory in MODULE_DIR:
        files = get_files(directory)

        for filename in [f.replace(".py", "") for f in files]:
            Bloxlink.get_module(path=directory, dir_name=filename)



if __name__ == "__main__":
    load_modules()

    bot = Bloxlink(env.get("DISCORD_PUBLIC_KEY", DISCORD_PUBLIC_KEY))
    bot.run(SERVER_HOST, SERVER_PORT, debug=True)
