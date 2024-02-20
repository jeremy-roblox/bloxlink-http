import logging
import asyncio

from pydantic import Field
from blacksheep import FromJSON, Request, ok, status_code
from blacksheep.server.controllers import APIController, get, post
from hikari import ForbiddenError
from bloxlink_lib.database import fetch_guild_data, redis
from bloxlink_lib import get_user_account, BaseModel, MemberSerializable, RobloxDown, StatusCodes

from resources import binds
from resources.bloxlink import instance as bloxlink
from resources.exceptions import BloxlinkForbidden

from ..decorators import authenticate


class UpdateUsersPayload(BaseModel):
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

    guild_id: int
    members: list[MemberSerializable]
    nonce: str


class MemberJoinPayload(BaseModel):
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

    member: MemberSerializable


class MinimalMember(BaseModel): # TODO: remove this
    id: str
    name: str
    discriminator: int = None
    avatar_url: str = None
    is_bot: bool = None
    created_at: str = None

    activity: str = None
    nickname: str = None
    guild_id: str = None
    guild_avatar: str = None
    permissions: int = None
    joined_at: str = None
    roles: list = Field(default_factory=list)
    is_owner: bool = None


class Update(APIController):
    """Results in a path of <URL>/api/update/..."""

    @get("/users")
    @authenticate()
    async def get_users(self, _request: Request):
        """Endpoint to get a user, just for testing availability currently."""
        return ok("GET request to this route was valid.")

    @post("/users")
    @authenticate()
    async def post_users(self, content: FromJSON[UpdateUsersPayload], _request: Request):
        """Endpoint to receive /verifyall user chunks from the gateway.

        Args:
            content (FromJSON[UpdateUsersPayload]): Request data from the gateway.
                See UpdateUsersPayload for expected JSON variables.
        """

        content: UpdateUsersPayload = content.value

        # Update users, send response only when this is done
        await process_update_members(content.members, content.guild_id, content.nonce)

        # TODO: We're currently waiting until this chunk is done before replying. This is likely not reliable
        # for the gateway to wait upon in the event of HTTP server reboots.
        # Either the gateway should TTL after some time frame, or we should reply with a 202 (accepted) as soon
        # as the request is received, with a way to check the status (like nonces?)
        return ok({
            "success": True
        })

    @post("/join/{guild_id}/{user_id}")
    @authenticate()
    async def update_on_join(
        self,
        guild_id: str,
        user_id: str,
        content: FromJSON[MemberJoinPayload],
        _request: Request,
    ):
        """Endpoint to handle guild member join events from the gateway.

        Args:
            guild_id (str): The guild ID the user joined.
            user_id (str): The ID of the user.
            user_data (FromJSON[MemberSerializable]): Additional user data from the gateway.
        """

        content: MemberJoinPayload = content.value
        member = content.member

        guild_data = await fetch_guild_data(
            guild_id, "autoRoles", "autoVerification", "highTrafficServer"
        )

        if guild_data.highTrafficServer:
            return status_code(StatusCodes.FORBIDDEN, {
                "error": "High traffic server is enabled, user was not updated."
            })

        if guild_data.autoVerification or guild_data.autoRoles:
            roblox_account = await get_user_account(user_id, guild_id=guild_id, raise_errors=False)
            bot_response = await binds.apply_binds(
                member,
                guild_id,
                roblox_account,
                moderate_user=True,
                update_embed_for_unverified=True,
                mention_roles=False
            )

            try:
                dm_channel = await bloxlink.rest.create_dm_channel(user_id)
                await dm_channel.send(embed=bot_response.embed, components=bot_response.action_rows)
            except ForbiddenError:
                pass

            return ok({
                "success": True,
            })

        return status_code(StatusCodes.FORBIDDEN, {
            "error": "This server has auto-roles disabled."
        })


async def process_update_members(members: list[MemberSerializable], guild_id: str, nonce: str):
    """Process a list of members to update from the gateway."""

    for member in members:
        if await redis.get(f"progress:{nonce}:cancelled"):
            raise asyncio.CancelledError

        if member.is_bot:
            continue

        logging.debug(f"Update endpoint: updating member: {member.username}")

        try:
            roblox_account = await get_user_account(member.id, guild_id=guild_id, raise_errors=False)
            await binds.apply_binds(member, guild_id, roblox_account, moderate_user=True)
        except (BloxlinkForbidden, RobloxDown):
            # bloxlink doesn't have permissions to give roles... might be good to
            # TODO: stop after n attempts where this is received so that way we don't flood discord with
            # 403 codes.
            continue

        await asyncio.sleep(1)

        # except RuntimeError as ex:
        #     # Nickname API error.
        #     success = False
        #     logging.error(ex)
        #     break

    # if content.is_done and success:
    #     # This is technically a lie since the gateway sends chunks of users, so the final chunk will likely
    #     # be processed along with other chunks, so the bot could potentially not be "done" yet.
    #     # Could be prevented with state tracking somehow? TBD

    #     await bloxlink.rest.create_message(channel_id, content="Your server has finished updating everyone!")
