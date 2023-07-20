from blacksheep import FromJSON, ok, Request, accepted
from blacksheep.server.controllers import APIController, get, post
from dataclasses import dataclass

from resources.bloxlink import instance as bloxlink
import resources.binds as binds
import resources.users as users

import asyncio


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
        content: UpdateBody = content.value

        # Update users in the background and instantly respond with 202 status.
        asyncio.create_task(_update_users(content))

        return accepted(f"OK. Received {content}")


async def _update_users(content: UpdateBody):
    members = content.members
    guild_id = content.guild_id
    channel_id = content.channel_id

    for member in members:
        if member.get("is_bot", False):
            continue

        print(f"Updating member: {member['name']}")

        roblox_account = await users.get_user_account(member["id"], guild_id=guild_id, raise_errors=False)
        message_response = await binds.apply_binds(member, guild_id, roblox_account, moderate_user=True)
        print(message_response)

    if content.is_done:
        await bloxlink.rest.create_message(channel_id, content="Your server has finished updating everyone!")
