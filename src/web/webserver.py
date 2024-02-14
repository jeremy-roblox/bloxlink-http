import logging
from blacksheep import Application, get
from asgi_prometheus import PrometheusMiddleware
# from prometheus_client import Counter, Histogram

webserver: Application = Application()
prom_webserver = PrometheusMiddleware(webserver, metrics_url="/", group_paths=['/'])


@webserver.after_start
async def after_start_print_routes(application: Application):
    """Prints all registered routes after the webserver starts"""

    logging.info(f"Routes registered: {dict(application.router.routes)}")


@get("/")
async def root():
    """Returns a 200 OK when the webserver is live"""

    return "The Bloxlink webserver is alive & responding."


webserver.mount("/metrics", prom_webserver)
