import asyncio
import logging
import time
from redis.asyncio import Redis  # pylint: disable=import-error

from config import CONFIG

redis: Redis = None

def connect_redis():
    """Connect to Redis."""

    global redis # pylint: disable=global-statement

    if CONFIG.REDIS_URL:
        redis = Redis.from_url(
            url=CONFIG.REDIS_URL,
            retry_on_timeout=True,
            decode_responses=True,
            health_check_interval=30,
        )
    else:
        redis = Redis(
            host=CONFIG.REDIS_HOST,
            port=CONFIG.REDIS_PORT,
            password=CONFIG.REDIS_PASSWORD,
            retry_on_timeout=True,
            decode_responses=True,
            health_check_interval=30,
        )

    # TODO: ping keepalive


class FutureMessage(asyncio.Future[dict]):
    """Represents a message from Redis in the future."""

    def __init__(self, created_at: int = time.time_ns()) -> None:
        super().__init__()
        self.created_at = created_at


class RedisMessageCollector:
    """Responsible for handling the bot's connection to Redis."""

    logger = logging.getLogger("redis.collector")

    def __init__(self):
        self.redis = redis
        self.pubsub = self.redis.pubsub()
        self._futures: dict[str, FutureMessage] = {}
        self._listener_task = asyncio.get_event_loop().create_task(self._listen_for_message())

    async def _listen_for_message(self):
        """Listen to messages over pubsub asynchronously"""
        self.logger.debug("Listening for messages.")
        while True:
            if not self.pubsub.subscribed:
                # Lets other events in the event loop trigger
                await asyncio.sleep(0)
                continue

            message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=10)
            if not message:
                await asyncio.sleep(0)
                continue

            # Required to be converted from a byte array.
            channel: str = message["channel"].decode("utf-8")
            future = self._futures.get(channel, None)
            if not future:
                continue  # We are not waiting for this message

            future.set_result(message)
            self.logger.debug(
                f"Fulfilled Future: {future} in {(time.time_ns() - future.created_at) / 1000000:.2f}ms"
            )
            await self.pubsub.unsubscribe(channel)
            self._futures.pop(channel)

    async def get_message(self, channel: str, timeout: int = 2):
        """Get a message from the given pubsub channel.

        Args:
            channel (str): Channel to listen to.
            timeout (int, optional): Time to wait for a response before the request fails in seconds.
                Defaults to 2 seconds.

        Raises:
            TimeoutError: When the channel cannot be subscribed to, or the timeout for a reply is reached.
        """
        future = self._futures.get(channel, None)
        if future:
            return await future

        future = FutureMessage()
        self._futures[channel] = future

        try:
            await asyncio.wait_for(self.pubsub.subscribe(channel), timeout=2)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Subscription of channel: {channel} took too long!") from None

        self.logger.debug(f"Waiting for {channel}")

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            # If the future is given a result, the channel is unsubscribed - but here, it is not.
            await self.pubsub.unsubscribe(channel)
            raise TimeoutError(f"No response was received on {channel}.") from None

connect_redis()
