from datetime import datetime, timedelta
from typing import Callable, Coroutine
import hikari
from motor.motor_asyncio import AsyncIOMotorClient
from redis import asyncio as redis
import asyncio
from inspect import iscoroutinefunction, isfunction
import logging
import importlib
import functools
from time import sleep
from queue import Queue
from threading import Lock
import uuid
import json

logger = logging.getLogger()

from .redis import get_message, send_message
from .commands import new_command
from .secrets import MONGO_URL, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from .models import UserData, GuildData

instance: 'Bloxlink' = None

class Bloxlink(hikari.RESTBot):
    def __init__(self, *args, **kwargs):
        global instance

        super().__init__(*args, **kwargs)

        self.mongo: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL); self.mongo.get_io_loop = asyncio.get_running_loop
        self.started_at = datetime.utcnow()
    
        instance = self

    @property
    def uptime(self) -> timedelta:
        return datetime.utcnow() - self.started_at

    async def fetch_item(self, domain: str, constructor: Callable, item_id: str, *aspects) -> object:
        """
        Fetch an item from local cache, then redis, then database.
        Will populate caches for later access
        """
        # should check local cache but for now just fetch from redis
        item = await self.mongo.bloxlink[domain].find_one({"_id": item_id}, {x:True for x in aspects}) or {"_id": item_id}

        if item.get("_id"):
            item.pop("_id")

        item["id"] = item_id

        return constructor(**item)

    async def update_item(self, domain: str, item_id: str, **aspects) -> None:
        """
        Update an item's aspects in local cache, redis, and database.
        """
        # # update redis cache
        # redis_aspects: dict = None
        # if any(isinstance(x, (dict, list)) for x in aspects.values()): # we don't save lists or dicts via redis
        #     redis_aspects = dict(aspects)

        #     for aspect_name, aspect_value in dict(aspects).items():
        #         if isinstance(aspect_value, (dict, list)):
        #             redis_aspects.pop(aspect_name)

        # await self.redis.hmset(f"{domain}:{item_id}", redis_aspects or aspects)

        # update database
        await self.mongo.bloxlink[domain].update_one({"_id": item_id}, {"$set": aspects}, upsert=True)


    async def new_fetch_member_data(guild_id: str, user_id: str, *fields) -> dict:
        nonce = uuid.uuid4()
        send_message("DEV.CACHE_LOOKUP", nonce, {
            "query": "guild.member",
            "data": {
                "guild_id": guild_id,
                "user_id": user_id
            }
        })
        msg = await get_message(f"DEV.REPLY.{nonce}", timeout=2)
        
        if not msg:
            raise NotImplementedError()
        
        return json.loads(msg["data"])

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

        for aspect_name, aspect in aspects.items(): # allow Discord objects to save by ID only
            if hasattr(aspect, "id"):
                aspects[aspect_name] = str(aspect.id)

        return await self.update_item("guilds", guild_id, **aspects)

    async def edit_user_roles(self, member: hikari.Member, guild_id: str | int, *, add_roles: list = None, remove_roles: list=None, reason: str = "") -> hikari.Member:
        """
        Adds or remove roles from a member.
        """

        new_roles = [r for r in member.roles if r not in remove_roles] + list(add_roles)

        return await self.rest.edit_member(user=member, guild=guild_id, roles=new_roles, reason=reason or "")

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
