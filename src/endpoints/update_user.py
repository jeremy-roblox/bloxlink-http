# from bot import webserver
from blacksheep import FromJSON, ok
from dataclasses import dataclass

# from resources.wb import instance as webserver
# from resources.bloxlink import webserver as app
from resources.webserver import instance as app
import hikari


@dataclass
class UpdateBody:
    guild_id: str
    channel_id: str
    members: list
    is_done: bool


@app.router.get("/api")
async def get_user():
    return ok("joe mama")


@app.router.post("/api/update/users")
async def update_users(content: FromJSON[UpdateBody]):
    print(content)
    return ok("Request been got")


@app.route("/")
async def bleh():
    return "Hello World!"
