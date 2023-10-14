import logging
from blacksheep import Application

instance: Application = Application()
logger = logging.getLogger()


@instance.after_start
async def after_start_print_routes(application: Application) -> None:
    logger.info(f"Routes registered: {dict(application.router.routes)}")


@instance.route("/")
async def root():
    return "The Bloxlink webserver is alive & responding."
