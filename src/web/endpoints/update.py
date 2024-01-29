import logging

from attrs import define, field
from blacksheep import FromJSON, Request, ok
from blacksheep.server.controllers import APIController, get, post
from hikari import ForbiddenError
from bot_utils.database import fetch_guild_data

from resources import binds
from resources.api.roblox import users
from resources.bloxlink import GuildData
from resources.bloxlink import instance as bloxlink
from resources.exceptions import BloxlinkForbidden, Message

from ..decorators import authenticate


@define
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


@define
class MinimalMember:
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
    roles: list = field(factory=list)
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
    async def post_users(self, content: FromJSON[UpdateBody], _request: Request):
        """Endpoint to receive /verifyall user chunks from the gateway.

        Args:
            content (FromJSON[UpdateBody]): Request data from the gateway.
                See UpdateBody for expected JSON variables.
        """

        content: UpdateBody = content.value

        # Update users, send response only when this is done (or there is an issue?)
        await _update_users(content)

        # NOTE: We're currently waiting until this chunk is done before replying. This is likely not reliable
        # for the gateway to wait upon in the event of HTTP server reboots.
        # Either the gateway should TTL after some time frame, or we should reply with a 202 (accepted) as soon
        # as the request is received, with a way to check the status (like nonces?)
        return ok(f"OK. Received {content}")

    @post("/join/{guild_id}/{user_id}")
    @authenticate()
    async def update_on_join(
        self,
        guild_id: str,
        user_id: str,
        user_data: FromJSON[MinimalMember],
        _request: Request,
    ):
        """Endpoint to handle guild member join events from the gateway.

        Args:
            guild_id (str): The guild ID the user joined.
            user_id (str): The ID of the user.
            user_data (FromJSON[MinimalMember]): Additional user data from the gateway.
        """
        user_data: MinimalMember = user_data.value
        guild_data: GuildData = await fetch_guild_data(
            guild_id, "autoRoles", "autoVerification", "highTrafficServer"
        )

        if guild_data.highTrafficServer:
            return ok("High traffic server is enabled, user was not updated.")

        if guild_data.autoVerification or guild_data.autoRoles:
            # print(user_data)
            roblox_account = await users.get_user_account(user_id, guild_id=guild_id, raise_errors=False)
            bot_response = await binds.apply_binds(
                {
                    "id": user_id,
                    "role_ids": user_data.roles,
                    "username": user_data.name,
                    "nickname": user_data.nickname,
                    "avatar_url": user_data.avatar_url,
                },
                guild_id,
                roblox_account,
                moderate_user=True,
                mention_roles=False,
                update_embed_for_unverified=True,
            )

            try:
                dm_channel = await bloxlink.rest.create_dm_channel(user_id)
                await dm_channel.send(embed=bot_response.embed, components=bot_response.action_rows)
            except ForbiddenError:
                pass

            return ok("User was updated in the server.")

        return ok("Server does not have auto-update features enabled.")


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
