from typing import Callable
import snowfin
from motor.motor_asyncio import AsyncIOMotorClient
from aredis import StrictRedis
from benedict import benedict

from .secrets import MONGO_URL, REDISHOST, REDISPORT, REDISPASSWORD
from .models import BloxlinkUser, BloxlinkGuild, PartialBloxlinkGuild, PartialBloxlinkUser

class Bloxlink(snowfin.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mongo = AsyncIOMotorClient(MONGO_URL)
        self.redis = StrictRedis(host=REDISHOST, port=REDISPORT, password=REDISPASSWORD)

        # self.cache = benedict(keypath_separator=":")

    async def fetch_item(self, domain: str, constructor: Callable, item_id: str) -> object:
        """
        Fetch an item from local cache, then redis, then database.
        Will populate caches for later access
        """
        # should check local cache but for now just fetch from redis
        item = await self.redis.hgetall(f"{domain}:{item_id}")

        if not item:
            item = await self.mongo.bloxlink[domain].find_one({"_id": item_id})

            if item:
                await self.redis.hmset(f"{domain}:{item_id}", item)

        return constructor(**item)

    async def update_item(self, domain: str, item_id: str, **aspects) -> None:
        """
        Update an item's aspects in local cache, redis, and database.
        """
        # update redis cache
        await self.redis.hmset(f"{domain}:{item_id}", aspects)

        # update database
        await self.mongo.bloxlink[domain].update_one({"_id": item_id}, {"$set": aspects})

    async def fetch_user(self, user_id: str) -> BloxlinkUser:
        """
        Fetch a full user from local cache, then redis, then database.
        Will populate caches for later access
        """
        return self.fetch_item("users", BloxlinkUser, user_id)

    async def fetch_guild(self, guild_id: str) -> BloxlinkGuild:
        """
        Fetch a full guild from local cache, then redis, then database.
        Will populate caches for later access
        """
        return self.fetch_item("guilds", BloxlinkGuild, guild_id)

    async def update_user(self, user_id: str, **aspects) -> None:
        """
        Update a user's aspects in local cache, redis, and database.
        """
        return self.update_item("users", user_id, **aspects)

    async def update_guild(self, guild_id: str, **aspects) -> None:
        """
        Update a guild's aspects in local cache, redis, and database.
        """
        return self.update_item("guilds", guild_id, **aspects)

        