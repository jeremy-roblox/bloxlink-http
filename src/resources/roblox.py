import re
from typing import Tuple

from utils import fetch
from bloxlink import instance as bot
from exceptions import RobloxNotFound

__all__ = (
    "get_roblox_id",
    "get_roblox_username",
    "validate_code",
)

nickname_template_regex = re.compile(r"\{(.*?)\}")
any_group_nickname = re.compile(r"\{group-rank-(.*?)\}")
bracket_search = re.compile(r"\[(.*)\]")
roblox_group_regex = re.compile(r"roblox.com/groups/(\d+)/")

API_URL = "https://api.roblox.com"
BASE_URL = "https://www.roblox.com"
GROUP_API = "https://groups.roblox.com"
THUMBNAIL_API = "https://thumbnails.roblox.com"

async def get_roblox_id(username) -> Tuple[str, str]:
    username_lower = username.lower()
    roblox_cached_data = await bot.redis(f"usernames_to_ids:{username_lower}")

    if roblox_cached_data:
        return roblox_cached_data

    json_data, response = await fetch(f"{API_URL}/users/get-by-username/?username={username}", raise_on_failure=True)

    if json_data.get("success") is False:
        raise RobloxNotFound

    correct_username, roblox_id = json_data.get("Username"), str(json_data.get("Id"))

    data = (roblox_id, correct_username)

    if correct_username:
        await bot.redis.set(f"usernames_to_ids:{username_lower}", data)

    return data

async def get_roblox_username(roblox_id) -> Tuple[str, str]:
    roblox_user = await bot.redis.get(f"roblox_users:{roblox_id}")

    if roblox_user and roblox_user.verified:
        return roblox_user.id, roblox_user.username

    json_data, response = await fetch(f"{API_URL}/users/{roblox_id}", raise_on_failure=True)

    if json_data.get("success") is False:
        raise RobloxNotFound

    correct_username, roblox_id = json_data.get("Username"), str(json_data.get("Id"))

    data = (roblox_id, correct_username)

    return data

async def validate_code(roblox_id, code):
    try:
        html_text, _ = await fetch(f"https://www.roblox.com/users/{roblox_id}/profile", raise_on_failure=True)
    except RobloxNotFound:
        raise Exception("You cannot link as a banned user. Please try again with another user.")

    return code in html_text