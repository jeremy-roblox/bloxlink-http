import asyncio
import functools
import importlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Callable, Coroutine, Optional

import hikari
import yuyo
from attrs import define, field
from motor.motor_asyncio import AsyncIOMotorClient
from redis import RedisError
from typing_extensions import Unpack

from resources.constants import DEFAULTS
from resources.redis import RedisMessageCollector, redis
from config import CONFIG

instance: "Bloxlink" = None


if TYPE_CHECKING:
    from resources.commands import NewCommandArgs


@define(slots=True)
class UserData:
    """Representation of a User's data in Bloxlink

    Attributes:
        id (int): The Discord ID of the user.
        robloxID (str): The roblox ID of the user's primary account.
        robloxAccounts (dict): All of the user's linked accounts, and any guild specific verifications.
    """

    id: int
    robloxID: str = None
    robloxAccounts: dict = field(factory=lambda: {"accounts": [], "guilds": {}, "confirms": {}})


@define(slots=True)
class GuildData:
    """Representation of the stored settings for a guild"""

    id: int
    binds: list = field(factory=list)  # FIXME

    verifiedRoleEnabled: bool = True
    verifiedRoleName: str = "Verified"  # deprecated
    verifiedRole: str = None

    unverifiedRoleEnabled: bool = True
    unverifiedRoleName: str = "Unverified"  # deprecated
    unverifiedRole: str = None

    ageLimit: int = None
    autoRoles: bool = None
    autoVerification: bool = None
    disallowAlts: bool = None
    disallowBanEvaders: str = None  # Site sets it to "ban" when enabled. Null when disabled.
    dynamicRoles: bool = None
    groupLock: dict = None
    highTrafficServer: bool = None

    nicknameTemplate: str = DEFAULTS.get("nicknameTemplate")

    premium: dict = field(factory=dict) # deprecated

    affiliate: dict = None

    # Old bind fields.
    roleBinds: dict = None
    groupIDs: dict = None
    converted_binds: bool = False


class Bloxlink(yuyo.AsgiBot):
    """The Bloxlink bot."""

    redis = redis

    def __init__(self, *args, **kwargs):
        """Initialize the bot & the MongoDB connection."""
        global instance  # pylint: disable=global-statement

        super().__init__(*args, **kwargs)
        self.started_at = datetime.utcnow()
        self.mongo: AsyncIOMotorClient = AsyncIOMotorClient(CONFIG.MONGO_URL)
        self.mongo.get_io_loop = asyncio.get_running_loop

        self.redis_messages: RedisMessageCollector = None

        instance = self

    async def start(self) -> Coroutine[any, any, None]:
        """Start the bot"""

        self.redis_messages = RedisMessageCollector()

        return await super().start()

    @property
    def uptime(self) -> timedelta:
        """Current bot uptime."""
        return datetime.utcnow() - self.started_at

    async def relay(self, channel: str, payload: Optional[dict] = None, timeout: int = 2) -> dict:
        """Relay a message over Redis to the gateway.

        Args:
            channel (str): The pubsub channel to publish the message over.
            payload (Optional[dict]): The data to include in the message being sent. Defaults to None.
            timeout (int, optional): Timeout time for a reply in seconds. Defaults to 2 seconds.

        Raises:
            RuntimeError: When Redis was unable to publish or get a response.
            TimeoutError: When the request has reached its timeout.

        Returns:
            dict: Response from the pubsub channel.
        """
        nonce = uuid.uuid4()
        reply_channel = f"REPLY:{nonce}"

        try:
            await self.redis_messages.pubsub.subscribe(reply_channel)
            await self.redis.publish(
                channel, json.dumps({"nonce": str(nonce), "data": payload}).encode("utf-8")
            )
            return await self.redis_messages.get_message(reply_channel, timeout=timeout)
        except RedisError as ex:
            raise RuntimeError("Failed to publish or wait for response") from ex
        except asyncio.TimeoutError as ex:
            raise TimeoutError("No response was received.") from ex

    async def fetch_discord_member(self, guild_id: int, user_id: int, *fields) -> dict | hikari.Member | None:
        """Get a discord member of a guild, first from the gateway, then from a HTTP request.

        Args:
            guild_id (int): The guild ID to find the user in.
            user_id (int): The user ID to find.

        Returns:
            dict | hikari.Member | None: User data as determined by the method of retrieval.
                Dict from the relay. hikari.Member from a HTTP request. None if the user was not found.
        """
        try:
            res = await self.relay(
                "CACHE_LOOKUP",
                {
                    "query": "guild.member",
                    "data": {"guild_id": guild_id, "user_id": user_id},
                    "fields": list(*fields),
                },
            )

            return json.loads(res.get("data").decode("utf-8"))
        except (RuntimeError, TimeoutError):
            try:
                return await self.rest.fetch_member(guild_id, user_id)
            except hikari.NotFoundError:
                return None

    async def fetch_discord_guild(self, guild_id: int) -> dict:
        """Fetches a discord guild from the gateway.

        Args:
            guild_id (int): The guild to find.

        Returns:
            dict: The found guild if it exists.
        """
        # TODO: Implement fallback to fetch from HTTP methods.

        res = await self.relay(
            "CACHE_LOOKUP",
            {
                "query": "guild.data",
                "data": {
                    "guild_id": guild_id,
                },
            },
        )
        return res["data"]

    async def fetch_item(self, domain: str, constructor: Callable, item_id: str, *aspects) -> object:
        """
        Fetch an item from local cache, then redis, then database.
        Will populate caches for later access
        """
        # TODO: Actually check redis and not just query mongodb.
        # should check local cache but for now just fetch from redis
        item = await self.mongo.bloxlink[domain].find_one({"_id": item_id}, {x: True for x in aspects}) or {
            "_id": item_id
        }

        if item.get("_id"):
            item.pop("_id")

        item["id"] = item_id

        return constructor(**item)

    async def update_item(self, domain: str, item_id: str, **aspects) -> None:
        """
        Update an item's aspects in local cache, redis, and database.
        """
        unset_aspects = {}
        set_aspects = {}
        for key, val in aspects.items():
            if val is None:
                unset_aspects[key] = ""
            else:
                set_aspects[key] = val

        # Update redis cache
        redis_set_aspects = {}
        redis_unset_aspects = {}

        for aspect_name, aspect_value in dict(aspects).items():
            if aspect_value is None:
                redis_unset_aspects[aspect_name] = aspect_value
            elif isinstance(aspect_value, (dict, list, bool)):
                pass
            else:
                redis_set_aspects[aspect_name] = aspect_value

        if redis_set_aspects:
            await redis.hset(f"{domain}:{item_id}", mapping=redis_set_aspects)
        if redis_unset_aspects:
            await redis.hdel(f"{domain}:{item_id}", *redis_unset_aspects.keys())

        # update database
        await self.mongo.bloxlink[domain].update_one(
            {"_id": item_id}, {"$set": set_aspects, "$unset": unset_aspects}, upsert=True
        )

    async def fetch_user_data(self, user: hikari.User | hikari.Member | str, *aspects) -> UserData:
        """
        Fetch a full user from local cache, then redis, then database.
        Will populate caches for later access
        """
        if isinstance(user, (hikari.User, hikari.Member)):
            user_id = str(user.id)
        else:
            user_id = str(user)

        return await self.fetch_item("users", UserData, user_id, *aspects)

    async def fetch_guild_data(self, guild: hikari.Guild | str, *aspects) -> GuildData:
        """
        Fetch a full guild from local cache, then redis, then database.
        Will populate caches for later access
        """

        if isinstance(guild, hikari.Guild):
            guild_id = str(guild.id)
        else:
            guild_id = str(guild)

        return await self.fetch_item("guilds", GuildData, guild_id, *aspects)

    async def update_user_data(self, user: hikari.User | hikari.Member, **aspects) -> None:
        """Update a user's aspects in local cache, redis, and database."""

        if isinstance(user, (hikari.User, hikari.Member)):
            user_id = str(user.id)
        else:
            user_id = str(user)

        return await self.update_item("users", user_id, **aspects)

    async def update_guild_data(self, guild: hikari.Guild | str, **aspects) -> None:
        """Update a guild's aspects in local cache, redis, and database."""

        if isinstance(guild, hikari.Guild):
            guild_id = str(guild.id)
        else:
            guild_id = str(guild)

        for aspect_name, aspect in aspects.items():  # allow Discord objects to save by ID only
            if hasattr(aspect, "id"):
                aspects[aspect_name] = str(aspect.id)

        return await self.update_item("guilds", guild_id, **aspects)

    async def edit_user_roles(
        self,
        member: hikari.Member,
        guild_id: str | int,
        *,
        add_roles: list = None,
        remove_roles: list = None,
        reason: str = "",
    ) -> hikari.Member:
        """Adds or remove roles from a member."""

        new_roles = [r for r in member.roles if r not in remove_roles] + list(add_roles)

        return await self.rest.edit_member(user=member, guild=guild_id, roles=new_roles, reason=reason or "")

    async def fetch_roles(self, guild_id: str | int):
        """guild.fetch_roles() but returns a nice dictionary instead"""
        return {str(role.id): role for role in await self.rest.fetch_roles(guild_id)}

    async def role_ids_to_names(self, guild_id: int, roles: list) -> str:
        """Get the names of roles based on the role ID.

        Args:
            guild_id (int): The guild to get the roles from.
            roles (list): The IDs of the roles to find the names for.

        Returns:
            str: Comma separated string of the names for all the role IDs given.
        """
        # TODO: Use redis -> gateway comms to get role data/role names.
        # For now this just makes a http request every time it needs it.

        guild_roles = await self.fetch_roles(guild_id)

        return ", ".join(
            [
                guild_roles.get(str(role_id)).name if guild_roles.get(str(role_id)) else "(Deleted Role)"
                for role_id in roles
            ]
        )

    async def reverse_lookup(self, roblox_id: int, origin_id: int | None = None) -> list[str]:
        """Find Discord IDs linked to a roblox id.

        Args:
            roblox_id (int): The roblox user ID that will be matched against.
            origin_id (int | None, optional): Discord user ID that will not be included in the output.
                Defaults to None.

        Returns:
            list[str]: All the discord IDs linked to this roblox_id.
        """
        cursor = self.mongo.bloxlink["users"].find(
            {"$or": [{"robloxID": roblox_id}, {"robloxAccounts.accounts": roblox_id}]},
            {"_id": 1},
        )

        return [x["_id"] async for x in cursor if str(origin_id) != str(x["_id"])]

    @staticmethod
    def load_module(import_name: str) -> None:
        """Utility function to import python modules.

        Args:
            import_name (str): Name of the module to import
        """

        logging.info(f"Attempting to load module {import_name}")

        try:
            module = importlib.import_module(import_name)

        except (ImportError, ModuleNotFoundError) as e:
            logging.error(f"Failed to import {import_name}: {e}")
            raise e

        except Exception as e:
            logging.error(f"Module {import_name} errored: {e}")
            raise e

        if hasattr(module, "__setup__"):
            try:
                if iscoroutinefunction(module.__setup__):
                    asyncio.run(module.__setup__())
                else:
                    module.__setup__()

            except Exception as e:
                logging.error(f"Module {import_name} errored: {e}")
                raise e

        logging.info(f"Loaded module {import_name}")

    @staticmethod
    def command(**command_attrs: "Unpack[NewCommandArgs]"):
        """Decorator to register a command."""

        from resources.commands import new_command # pylint: disable=import-outside-toplevel

        def wrapper(*args, **kwargs):
            return new_command(*args, **kwargs, **command_attrs)

        return wrapper

    @staticmethod
    def subcommand(**kwargs):
        """Decorator to register a subcommand."""

        def decorator(f):
            f.__issubcommand__ = True
            f.__subcommandattrs__ = kwargs

            @functools.wraps(f)
            def wrapper(self, *args):
                return f(self, *args)

            return wrapper

        return decorator
