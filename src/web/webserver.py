import logging

from blacksheep import Application, Request, unauthorized

from config import SERVER_AUTH

instance: Application = Application()

logger = logging.getLogger()


async def simple_auth(request: Request, handler):
    """
    Simple way of ensuring that only valid requests can be sent to the bot
    via the Authorization header.
    """
    auth_header = request.get_first_header(b"Authorization")
    unauth = unauthorized("You are not authorized to use this endpoint.")

    if not auth_header:
        return unauth

    auth_header = auth_header.decode()
    if auth_header != SERVER_AUTH:
        return unauth

    response = await handler(request)
    return response


instance.middlewares.append(simple_auth)


@instance.after_start
async def after_start_print_routes(application: Application) -> None:
    logger.info(f"Routes registered: {dict(application.router.routes)}")


@instance.route("/")
async def root():
    return "The Bloxlink webserver is alive & responding."
