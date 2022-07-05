from datetime import datetime, timedelta
from typing import Callable
import snowfin
from motor.motor_asyncio import AsyncIOMotorClient
from redis import asyncio as redis
import asyncio

from .secrets import MONGO_URL, REDISHOST, REDISPORT, REDISPASSWORD, DISCORD_APPLICATION_ID, DISCORD_TOKEN
from .models import BloxlinkUser, BloxlinkGuild

instance: 'Bloxlink' = None

class Bloxlink(snowfin.Client):
    def __init__(self, *args, **kwargs):
        global instance

        super().__init__(*args, **kwargs)

        self.mongo: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL); self.mongo.get_io_loop = asyncio.get_running_loop
        self.redis: redis.Redis = redis.Redis(host=REDISHOST, port=REDISPORT, password=REDISPASSWORD, decode_responses=True)

        self.started_at = datetime.utcnow()
        # self.http = snowfin.http.HTTP(DISCORD_APPLICATION_ID, token=DISCORD_TOKEN)

        instance = self
        # self.cache = benedict(keypath_separator=":")

    @property
    def uptime(self) -> timedelta:
        return datetime.utcnow() - self.started_at

    async def fetch_item(self, domain: str, constructor: Callable, item_id: str, *aspects) -> object:
        """
        Fetch an item from local cache, then redis, then database.
        Will populate caches for later access
        """
        # should check local cache but for now just fetch from redis

        if aspects:
            item = await self.redis.hmget(f"{domain}:{item_id}", *aspects)
            item = {x: y for x, y in zip(aspects, item) if y is not None}
        else:
            item = await self.redis.hgetall(f"{domain}:{item_id}")

        if not item:
            item = await self.mongo.bloxlink[domain].find_one({"_id": item_id}, {x:True for x in aspects}) or {"_id": item_id}

            if item and not isinstance(item, (list, dict)):
                if aspects:
                    items = {x:item[x] for x in aspects if item.get(x) and not isinstance(item[x], dict)}
                    if items:
                        await self.redis.hset(f"{domain}:{item_id}", items)
                else:
                    await self.redis.hset(f"{domain}:{item_id}", item)

        if item.get("_id"):
            item.pop("_id")

        item["id"] = item_id

        return constructor(**item)

    async def update_item(self, domain: str, item_id: str, **aspects) -> None:
        """
        Update an item's aspects in local cache, redis, and database.
        """
        # update redis cache
        await self.redis.hmset(f"{domain}:{item_id}", aspects)

        # update database
        await self.mongo.bloxlink[domain].update_one({"_id": item_id}, {"$set": aspects})

    async def fetch_user(self, user_id: str, *aspects) -> BloxlinkUser:
        """
        Fetch a full user from local cache, then redis, then database.
        Will populate caches for later access
        """
        return await self.fetch_item("users", BloxlinkUser, user_id, *aspects)

    async def fetch_guild(self, guild_id: str, *aspects) -> BloxlinkGuild:
        """
        Fetch a full guild from local cache, then redis, then database.
        Will populate caches for later access
        """
        return await self.fetch_item("guilds", BloxlinkGuild, guild_id, *aspects)

    async def update_user(self, user_id: str, **aspects) -> None:
        """
        Update a user's aspects in local cache, redis, and database.
        """
        return await self.update_item("users", user_id, **aspects)

    async def update_guild(self, guild_id: str, **aspects) -> None:
        """
        Update a guild's aspects in local cache, redis, and database.
        """
        return await self.update_item("guilds", guild_id, **aspects)

    async def fetch_roles(self, guild_id: str) -> list:
        """
        Fetch the guild's roles. Not cached.
        """

        r = snowfin.http.Route(
            "GET",
            "/guilds/{guild_id}/roles",
            guild_id=guild_id,
            auth=True
        )

        return await self.http.request(r)
