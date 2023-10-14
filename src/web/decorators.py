from functools import wraps
from blacksheep import Request, unauthorized
from resources.secrets import SERVER_AUTH  # pylint: disable=no-name-in-module
from blacksheep.server.normalization import ensure_response
import logging

logger = logging.getLogger()

UNAUTHORIZED_RESPONSE = unauthorized("You are not authorized to use this endpoint.")


def authenticate():
    def decorator(handler):
        @wraps(handler)
        async def wrapped(endpoint, request: Request):
            auth_header = request.get_first_header(b"Authorization").decode() if request.has_header(b"Authorization") else None

            # In case we ever omit the server auth config, we forbid all requests.
            if not SERVER_AUTH:
                logger.error("No SERVER_AUTH was set! Blocking all requests.")
                return UNAUTHORIZED_RESPONSE

            if auth_header != SERVER_AUTH:
                return UNAUTHORIZED_RESPONSE

            response = ensure_response(await handler(endpoint, request))

            return response

        return wrapped

    return decorator
