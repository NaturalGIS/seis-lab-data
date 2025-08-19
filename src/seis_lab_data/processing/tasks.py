import logging

import dramatiq

from .. import config

logger = logging.getLogger(__name__)


@dramatiq.actor
def process_data(message: str):
    settings = config.get_settings()
    logger.debug(
        f"Received message: {message} - Also settings.debug is {settings.debug}"
    )
