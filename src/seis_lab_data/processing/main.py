import logging

from ..config import SeisLabDataCliContext

logger = logging.getLogger(__name__)


def message_handler(message: dict, *, context: SeisLabDataCliContext):
    logger.debug(f"received message: {message}")
