import asyncio
import functools
import importlib
import json
import logging
import uuid
from datetime import datetime, timedelta
from inspect import iscoroutinefunction
from typing import Callable, Coroutine, Optional

import hikari
import yuyo
from motor.motor_asyncio import AsyncIOMotorClient
from redis import asyncio as redis

logger = logging.getLogger()

from resources.redis import RedisMessageCollector

from .commands import new_command
from .models import GuildData, UserData
from .secrets import MONGO_URL, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

instance: "Bloxlink" = None


class Bloxlink(yuyo.AsgiBot):
    def __init__(self, *args, **kwargs):
        global instance

        super().__init__(*args, **kwargs)
        self.started_at = datetime.utcnow()
        self.mongo: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL)
        self.mongo.get_io_loop = asyncio.get_running_loop

        instance = self

    async def start(self) -> Coroutine[any, any, None]:
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)
        self.redis_messages = RedisMessageCollector(self.redis)

        return await super().start()

    @property
    def uptime(self) -> timedelta:
        return datetime.utcnow() - self.started_at

    async def relay(self, channel: str, payload: Optional[dict] = None, timeout: int = 2) -> dict:
        nonce = uuid.uuid4()
        reply_channel = f"REPLY:{nonce}"

        try:
            await self.redis_messages.pubsub.subscribe(reply_channel)
            await self.redis.publish(
                channel, json.dumps({"nonce": str(nonce), "data": payload}).encode("utf-8")
            )
            return await self.redis_messages.get_message(reply_channel, timeout=timeout)
        except redis.RedisError as ex:
            raise RuntimeError("Failed to publish or wait for response") from ex
        except asyncio.TimeoutError as ex:
            raise TimeoutError("No response was recieved.") from ex

    async def fetch_discord_member(self, guild_id: int, user_id: int, *fields) -> dict | hikari.Member | None:
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
        # update redis cache
        redis_aspects = dict(aspects)

        # we don't save lists and dicts to redis
        for aspect_name, aspect_value in dict(aspects).items():
            if isinstance(aspect_value, (dict, list)):
                redis_aspects.pop(aspect_name)

        if redis_aspects:
            await self.redis.hmset(f"{domain}:{item_id}", redis_aspects)

        # update database
        await self.mongo.bloxlink[domain].update_one({"_id": item_id}, {"$set": aspects}, upsert=True)

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
        """
        Update a user's aspects in local cache, redis, and database.
        """

        if isinstance(user, (hikari.User, hikari.Member)):
            user_id = str(user.id)
        else:
            user_id = str(user)

        return await self.update_item("users", user_id, **aspects)

    async def update_guild_data(self, guild: hikari.Guild | str, **aspects) -> None:
        """
        Update a guild's aspects in local cache, redis, and database.
        """

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
        """
        Adds or remove roles from a member.
        """

        new_roles = [r for r in member.roles if r not in remove_roles] + list(add_roles)

        return await self.rest.edit_member(user=member, guild=guild_id, roles=new_roles, reason=reason or "")

    async def fetch_roles(self, guild_id: str | int):
        """
        guild.fetch_roles() but returns a nice dictionary instead

        """
        return {str(role.id): role for role in await self.rest.fetch_roles(guild_id)}

    async def role_ids_to_names(self, guild_id: int, roles: list) -> str:
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
        try:
            module = importlib.import_module(import_name)

        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"Failed to import {import_name}: {e}")
            raise e

        except Exception as e:
            logger.error(f"Module {import_name} errored: {e}")
            raise e

        if hasattr(module, "__setup__"):
            try:
                if iscoroutinefunction(module.__setup__):
                    asyncio.run(module.__setup__())
                else:
                    module.__setup__()

            except Exception as e:
                logger.error(f"Module {import_name} errored: {e}")
                raise e

        logging.info(f"Loaded module {import_name}")

    @staticmethod
    def command(**command_attrs):
        def wrapper(*args, **kwargs):
            return new_command(*args, **kwargs, **command_attrs)

        return wrapper

    @staticmethod
    def subcommand(**kwargs):
        def decorator(f):
            f.__issubcommand__ = True
            f.__subcommandattrs__ = kwargs

            @functools.wraps(f)
            def wrapper(self, *args):
                return f(self, *args)

            return wrapper

        return decorator
