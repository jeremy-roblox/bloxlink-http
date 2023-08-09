import asyncio
import logging
from dataclasses import dataclass

from blacksheep import FromJSON, Request, accepted, ok
from blacksheep.server.controllers import APIController, get, post

import resources.binds as binds
import resources.roblox.users as users
from resources.bloxlink import instance as bloxlink
from resources.exceptions import BloxlinkForbidden, Message


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
    """Results in a path of <URL>/api/update/..."""

    @get("/users")
    async def get_user(self, request: Request):
        return ok("GET request to this route was valid.")

    @post("/users")
    async def post_user(content: FromJSON[UpdateBody]):
        content: UpdateBody = content.value

        # Update users, send response only when this is done (or there is an issue?)
        await _update_users(content)

        return accepted(f"OK. Received {content}")


async def _update_users(content: UpdateBody):
    members = content.members
    guild_id = content.guild_id
    channel_id = content.channel_id
    success = True

    for member in members:
        if member.get("is_bot", False):
            continue

        logging.debug(f"Updating member: {member['name']}")

        try:
            roblox_account = await users.get_user_account(member["id"], guild_id=guild_id, raise_errors=False)
            await binds.apply_binds(member, guild_id, roblox_account, moderate_user=True)
        except BloxlinkForbidden:
            # bloxlink doesn't have permissions to give roles... might be good to
            # stop after n attempts where this is received so that way we don't flood discord with
            # 403 codes.
            continue

        except Message as ex:
            # Binds API error.
            logging.error(ex)
            continue

        except RuntimeError as ex:
            # Nickname API error.
            success = False
            logging.error(ex)
            break

    if content.is_done and success:
        # This is technically a lie since the gateway sends chunks of users, so the final chunk will likely
        # be processed along with other chunks, so the bot could potentially not be "done" yet.
        # Could be prevented with state tracking somehow? TBD

        await bloxlink.rest.create_message(channel_id, content="Your server has finished updating everyone!")
