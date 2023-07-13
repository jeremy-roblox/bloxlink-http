from blacksheep import FromJSON, ok, Request
from blacksheep.server.controllers import APIController, get, post
from dataclasses import dataclass
import hikari


@dataclass
class UpdateBody:
    """
    The expected content when a request from the gateway -> the server
    is made regarding updating a chunk of users.

    guild_id (str): ID of the guild were users should be updated.
    channel_id (str): ID of the channel that the bot should send a message to when done.
    members (list): List of cached members, each element should
        represent a type reflecting a hikari.Member object (JSON representation?).
    is_done (bool): Used to tell the server if it is done sending chunks for this session, so on complete send
        the message saying the scan is complete.
    """

    guild_id: str
    channel_id: str
    members: list
    is_done: bool = False


class Update(APIController):
    @get("/users")
    async def get_user(self, request: Request):
        return ok("GET request to this route was valid.")

    @post("/users")
    async def post_user(content: FromJSON[UpdateBody]):
        content = content.value
        # TODO: for each member in content.members, convert to hikari member & apply binds
        # Need to decide if the gateway could just send a bunch of chunks at once, or if it
        # should send one at a time, waiting for the reply (for an OK) before trying again

        # Might also need a way to tell the gateway to stop if necessary?
        return ok(f"POST request to this route was valid. Recieved {content}")
