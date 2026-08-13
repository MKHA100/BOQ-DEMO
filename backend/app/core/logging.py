import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs the complete request URL at INFO level. Roboflow's hosted
    # endpoint currently receives the private API key as a query parameter, so
    # suppress transport-level request URLs to prevent secrets appearing in
    # worker logs. Application-level failures are still logged by the worker.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
