import time
import asyncio
import redis
import threading
import uuid
import json
import logging

from resources.secrets import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD


__all__ = [
    "get_message",
    "send_message"
]

REDIS = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)
PUBSUB = REDIS.pubsub()
WAITING_MESSAGES: dict[str, dict | None] = {} 
WAITING_MESSAGES_LOCK = threading.Lock()

def _listen_for_message():
    while True:
        message = PUBSUB.get_message()
        
        if message:
            with WAITING_MESSAGES_LOCK:
                message_channel: str = message["channel"]
                if message_channel in WAITING_MESSAGES:
                    WAITING_MESSAGES[message_channel] = message
        time.sleep(0.05)
        
threading.Thread(None, lambda: _listen_for_message())

def _wait_message(channel: str) -> dict:
    while True:
        with WAITING_MESSAGES_LOCK:
            message = WAITING_MESSAGES.get(channel, None)
            if message: 
                WAITING_MESSAGES.pop(channel)
                return message
        time.sleep(0.05)

async def get_message(channel: str, timeout: int = 2, unsubscribe: bool = True) -> dict | None:
    if not channel in PUBSUB.channels:
        PUBSUB.subscribe(channel)
        
    if channel in WAITING_MESSAGES:
        raise NotImplementedError()
    
    WAITING_MESSAGES[channel] = None
    my_task = asyncio.create_task(lambda: _wait_message(channel, timeout))
    
    msg = None
    try:
        msg = await asyncio.wait_for(my_task, timeout)
    except TimeoutError:
        pass
    
    if unsubscribe:
        PUBSUB.unsubscribe(channel)
    return msg

def send_message(channel: str, nonce: uuid.UUID, payload: dict | list | None = None):
    received = REDIS.publish(channel, json.dumps({
        "nonce": nonce,
        "data": payload
    }))
    
    if received < 1:
        logging.warn(f"Published message on {channel} with no subscriptions")