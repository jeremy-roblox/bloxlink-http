import asyncio
import logging
import time
import json
from redis.asyncio import Redis  # pylint: disable=import-error
from bloxlink_lib import create_task_log_exception, get_node_count, BaseModel, parse_into

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
        self._futures: dict[str, tuple[FutureMessage, bool, BaseModel | dict, list[dict]]] = {}
        self._listener_task = create_task_log_exception(self._listen_for_message())

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
                continue

            # Required to be converted from a byte array.
            channel: str = message["channel"]
            current_future = self._futures.get(channel, None)

            if not current_future:
                continue  # We are not waiting for this message

            future, wait_for_all, model, current_results = current_future

            current_results.append(parse_into(json.loads(message["data"]), model))

            if not wait_for_all or len(current_results) == get_node_count():
                self._futures.pop(channel, None)
                future.set_result(current_results)

            self.logger.debug(
                f"Fulfilled Future: {future} in {(time.time_ns() - future.created_at) / 1000000:.2f}ms"
            )

    async def get_message[T](self, channel: str, timeout: int, wait_for_all: bool, model: T = None) -> list[T]:
        """Get a message from the given pubsub channel.

        Args:
            channel (str): Channel to listen to.
            timeout (int, optional): Time to wait for a response before the request fails in seconds.
                Defaults to 2 seconds.

        Raises:
            TimeoutError: When the channel cannot be subscribed to, or the timeout for a reply is reached.
        """

        future = self._futures.get(channel, None)
        model = model or dict

        if future:
            return await future

        future = FutureMessage()
        self._futures[channel] = (future, wait_for_all, model, [])

        await self.pubsub.subscribe(channel)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            await self.pubsub.unsubscribe(channel)


connect_redis()
