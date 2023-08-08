import asyncio
import logging
import threading
import time

from redis.asyncio import Redis


class FutureMessage(asyncio.Future[dict]):
    def __init__(self, created_at: int = time.time_ns()) -> None:
        super().__init__()
        self.created_at = created_at


class RedisMessageCollector:
    logger = logging.getLogger("redis.collector")

    def __init__(self, redis: Redis):
        self.redis = redis
        self.pubsub = self.redis.pubsub()
        self._futures: dict[str, FutureMessage] = {}
        self._listener_task = asyncio.get_event_loop().create_task(self._listen_for_message())

    async def _listen_for_message(self):
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
        future = self._futures.get(channel, None)
        if future:
            return await future

        future = FutureMessage()
        self._futures[channel] = future

        try:
            await asyncio.wait_for(self.pubsub.subscribe(channel), timeout=2)
        except TimeoutError:
            raise TimeoutError(f"Subscription of channel: {channel} took too long!")

        self.logger.debug(f"Waiting for {channel}")
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError as ex:
            # If the future is given a result, the channel is unsubscribed - but here, it is not.
            await self.pubsub.unsubscribe(channel)
            raise ex
