from os import environ as env
from resources.constants import DISCORD_PUBLIC_KEY, SERVER_HOST, SERVER_PORT
from resources.structures import Bloxlink

bot = Bloxlink(env.get("DISCORD_PUBLIC_KEY", DISCORD_PUBLIC_KEY))



if __name__ == "__main__":
    bot.run(SERVER_HOST, SERVER_PORT, debug=True)
