import logging
from blacksheep import Application
from asgi_prometheus import PrometheusMiddleware
from prometheus_client import Counter, Histogram

webserver: Application = Application()
prom_webserver = PrometheusMiddleware(webserver, metrics_url="/", group_paths=['/'])

logger = logging.getLogger()


@webserver.after_start
async def after_start_print_routes(application: Application) -> None:
    logger.info(f"Routes registered: {dict(application.router.routes)}")


@webserver.route("/")
async def root():
    return "The Bloxlink webserver is alive & responding."


webserver.mount("/metrics", prom_webserver)
