import asyncio
import logging
from typing import Literal
from enum import IntEnum

import aiohttp
from requests.utils import requote_uri

from resources.exceptions import RobloxAPIError, RobloxDown, RobloxNotFound
from config import CONFIG

__all__ = ("fetch", "StatusCodes")


session = None

class StatusCodes(IntEnum):
    """Status codes for requests"""

    OK = 200
    NOT_FOUND = 404
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


async def fetch(
    method: str,
    url: str,
    *,
    params: dict = None,
    headers: dict = None,
    body: dict = None,
    parse_as: Literal["JSON", "BYTES", "TEXT"] = "JSON",
    raise_on_failure: bool = True,
    timeout: float = 10,
):
    """Make a REST request with the ability to proxy.

    Only Roblox URLs are proxied, all other requests to other domains are sent as is.

    Args:
        method (str): The HTTP request method to use for this query.
        url (str): The URL to send the request to.
        params (dict, optional): Query parameters to append to the URL. Defaults to None.
        headers (dict, optional): Headers to use when sending the request. Defaults to None.
        body (dict, optional): Data to pass in the body of the request. Defaults to None.
        parse_as (JSON | BYTES | TEXT, optional): Set what the expected type to return should be.
            Defaults to JSON.
        raise_on_failure (bool, optional): Whether an exception be raised if the request fails. Defaults to True.
        timeout (float, optional): How long should we wait for a request to succeed. Defaults to 10 seconds.

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
    global session  # pylint: disable=global-statement

    params = params or {}
    headers = headers or {}

    if not session:
        session = aiohttp.ClientSession()

    url = requote_uri(url)

    for k, v in params.items():
        if isinstance(v, bool):
            params[k] = "true" if v else "false"

    try:
        async with session.request(
            method,
            url,
            json=body,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout) if timeout else None,
            proxy=CONFIG.PROXY_URL if CONFIG.PROXY_URL and "roblox.com" in url else None,
        ) as response:
            if response.status != StatusCodes.OK and raise_on_failure:
                if response.status == StatusCodes.SERVICE_UNAVAILABLE:
                    raise RobloxDown()

                if response.status == StatusCodes.NOT_FOUND:
                    raise RobloxNotFound()

                raise RobloxAPIError(f"{url} failed with status {response.status} and body {await response.text()}")

            if parse_as == "TEXT":
                return await response.text(), response

            if parse_as == "JSON":
                try:
                    json = await response.json()
                except aiohttp.client_exceptions.ContentTypeError as exc:
                    logging.debug(url, await response.text(), flush=True)

                    raise RobloxAPIError() from exc

                return json, response

            if parse_as == "BYTES":
                return await response.read(), response


            return response

    except asyncio.TimeoutError:
        logging.debug(f"URL {url} timed out")
        raise RobloxDown() from None
