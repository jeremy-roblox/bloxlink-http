import asyncio
from enum import Enum
from json import JSONDecodeError, loads
from typing import Iterable, Callable
from attrs import field
import copy

import aiohttp
from requests.utils import requote_uri

from resources.exceptions import RobloxAPIError, RobloxDown, RobloxNotFound
from resources.secrets import PROXY_URL  # pylint: disable=no-name-in-module

__all__ = ("fetch", "ReturnType", "default_field")

session = None


class ReturnType(Enum):
    JSON = 1
    TEXT = 2
    BYTES = 3


async def fetch(
    method: str,
    url: str,
    params: dict = None,
    headers: dict = None,
    body: dict = None,
    return_data: ReturnType = ReturnType.JSON,
    raise_on_failure: bool = True,
    timeout: float = 20,
    proxy: bool = True,
):
    """Utility function to make a REST request (with the ability to proxy)

    Only Roblox URLs are proxied, all other requests to other domains are sent as is.

    Args:
        method (str): The HTTP request method to use for this query.
        url (str): The URL to send the request to.
        params (dict, optional): Query parameters to append to the URL. Defaults to None.
        headers (dict, optional): Headers to use when sending the request. Defaults to None.
        body (dict, optional): Data to pass in the body of the request. Defaults to None.
        return_data (ReturnType, optional): Set what the expected type to return should be.
            Defaults to ReturnType.JSON.
        raise_on_failure (bool, optional): Should an exception be raised if the request fails. Defaults to True.
        timeout (float, optional): How long should we wait for a request to succeed. Defaults to 20.
        proxy (bool, optional): Should we try proxying this request. Defaults to True.
            The proxy only applies to Roblox URLs.

    Raises:
        RobloxAPIError:
            For proxied requests, raised when the proxy server returns a data format that is not JSON.
            When a request returns a status code that is NOT 503 or 404, but is over 400 (if raise_on_failure).
            When a non-proxied request does not match the expected data type (typically JSON).
        RobloxDown: Raised if raise_on_failure, and the status code is 503. Also raised on request timeout.
        RobloxNotFound: Raised if raise_on_failure, and the status code is 404.

    Returns:
        (dict, str, bytes): The requested data from the request, if any.
    """
    params = params or {}
    headers = headers or {}
    new_json = {}
    proxied = False

    global session  # pylint: disable=global-statement

    if not session:
        session = aiohttp.ClientSession()

    if proxy and PROXY_URL and "roblox.com" in url:
        old_url = url
        new_json["url"] = url
        new_json["data"] = body or {}
        url = PROXY_URL
        proxied = True
        method = "POST"

    else:
        new_json = body
        old_url = url

    url = requote_uri(url)

    for k, v in params.items():
        if isinstance(v, bool):
            params[k] = "true" if v else "false"

    try:
        async with session.request(
            method,
            url,
            json=new_json,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout) if timeout else None,
        ) as response:
            if proxied:
                try:
                    response_json = await response.json()
                except aiohttp.client_exceptions.ContentTypeError as exc:
                    raise RobloxAPIError("Proxy server returned invalid JSON.") from exc

                response_body = response_json["req"]["body"]
                response_status = response_json["req"]["status"]
                response.status = response_status

                if not isinstance(response_body, dict):
                    try:
                        response_body_json = loads(response_body)
                    except JSONDecodeError:
                        pass
                    else:
                        response_body = response_body_json
            else:
                response_status = response.status
                response_body = None

            if raise_on_failure:
                if response_status == 503:
                    raise RobloxDown()
                elif response_status == 404:
                    raise RobloxNotFound()
                elif response_status >= 400:
                    if proxied:
                        print(old_url, response_body, flush=True)
                    else:
                        print(old_url, await response.text(), flush=True)
                    raise RobloxAPIError()

                if return_data is ReturnType.JSON:
                    if not proxied:
                        try:
                            response_body = await response.json()
                        except aiohttp.client_exceptions.ContentTypeError as exc:
                            raise RobloxAPIError() from exc

                    if isinstance(response_body, dict):
                        return response_body, response
                    else:
                        return {}, response

            if return_data is ReturnType.TEXT:
                if proxied:
                    return str(response_body), response

                text = await response.text()

                return text, response

            elif return_data is ReturnType.JSON:
                if proxied:
                    if not isinstance(response_body, dict):
                        print("Roblox API Error: ", old_url, type(response_body), response_body, flush=True)

                        if raise_on_failure:
                            raise RobloxAPIError()

                    return response_body, response

                try:
                    json = await response.json()
                except aiohttp.client_exceptions.ContentTypeError as exc:
                    print(old_url, await response.text(), flush=True)

                    raise RobloxAPIError() from exc

                return json, response

            elif return_data is ReturnType.BYTES:
                return await response.read(), response

            return response

    except asyncio.TimeoutError:
        print(f"URL {old_url} timed out", flush=True)
        raise RobloxDown() from None

def default_field(obj: list | dict):
    return field(factory=lambda: copy.copy(obj))

def find(predicate: Callable, iterable: Iterable):
    for element in iterable:
        if predicate(element):
            return element

    return None
