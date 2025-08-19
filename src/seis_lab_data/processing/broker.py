import logging

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from .. import config

logger = logging.getLogger(__name__)


def setup_broker(settings: config.SeisLabDataSettings | None = None) -> None:
    settings = settings or config.get_settings()
    broker = RedisBroker(
        host=settings.message_broker_dsn.host,
        port=settings.message_broker_dsn.port,
    )
    dramatiq.set_broker(broker)
