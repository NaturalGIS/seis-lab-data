import asyncio
import logging
import typing

import dramatiq
from sqlalchemy.ext.asyncio import AsyncEngine
from redis.asyncio import Redis

from ..config import (
    get_settings,
    SeisLabDataSettings,
)
from ..db.engine import (
    get_engine,
    get_session_maker,
)

logger = logging.getLogger(__name__)


class SeisLabDataSettingsMiddleware(dramatiq.Middleware):
    """
    Dramatiq middleware that stores the settings at worker initialization.
    """

    sld_settings: SeisLabDataSettings | None

    def __init__(self, settings: SeisLabDataSettings):
        self.sld_settings = None

    def after_process_boot(self, broker: dramatiq.Broker):
        """Hook called after a worker process boots.

        Initializes the async Redis client.
        """
        logger.info("Initializing SeisLabData settings...")
        self.sld_settings = get_settings()


class AsyncSqlAlchemyDbMiddleware(dramatiq.Middleware):
    """
    Dramatiq middleware that manages the lifecycle of sqlalchemy async engine.
    """

    _db_dsn: str
    _debug: bool
    engine: AsyncEngine | None
    session_maker: typing.Callable | None

    def __init__(self, db_dsn: str, debug: bool = False):
        self._db_dsn = db_dsn
        self._debug = debug
        self.engine = None
        self.session_maker = None

    def after_process_boot(self, broker: dramatiq.Broker):
        """Hook called after a worker process boots.

        Initialize the async sqlalchemy session.
        """
        logger.info("Initializing sqlalchemy engine...")
        self.engine = get_engine(self._db_dsn, self._debug)
        self.session_maker = get_session_maker(self.engine)
        logger.debug("sqlalchemy engine initialized.")

    def after_worker_shutdown(self, broker: dramatiq.Broker, worker: dramatiq.Worker):
        """Hook called after a worker process shuts down.

        Closes the async Redis client.
        """
        logger.info("Disposing of sqlalchemy engine...")
        if self.engine:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.engine.dispose())
            logger.debug("sqlalchemy engine disposed.")
        self.engine = None
        self.session_maker = None


class AsyncRedisPubSubMiddleware(dramatiq.Middleware):
    """
    Dramatiq middleware that manages the lifecycle of a redis client for async pub/sub.
    """

    _redis_dsn: str
    redis_client: Redis | None

    def __init__(self, redis_dsn: str):
        self._redis_dsn = redis_dsn
        self.redis_client = None

    def after_process_boot(self, broker: dramatiq.Broker):
        """Hook called after a worker process boots.

        Initializes the async Redis client.
        """
        logger.info("Initializing Redis PubSub client...")
        loop = asyncio.get_event_loop()
        self.redis_client = loop.run_until_complete(Redis.from_url(self._redis_dsn))
        logger.debug("Redis PubSub client initialized.")

    def after_worker_shutdown(self, broker: dramatiq.Broker, worker: dramatiq.Worker):
        """Hook called after a worker process shuts down.

        Closes the async Redis client.
        """
        logger.info("Closing Redis PubSub client...")
        if self.redis_client:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.redis_client.aclose())
            logger.debug("Redis PubSub client closed.")
        self.redis_client = None
