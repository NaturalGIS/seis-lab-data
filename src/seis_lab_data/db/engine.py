import sqlmodel
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio.session import async_sessionmaker
from sqlalchemy.ext.asyncio.engine import (
    AsyncEngine,
    create_async_engine,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import SeisLabDataSettings

_DB_ENGINE: AsyncEngine | None = None
_SYNC_DB_ENGINE: AsyncEngine | None = None


def get_engine(db_dsn: str, debug: bool = False) -> AsyncEngine:
    # This function implements caching of the sqlalchemy engine, relying on the
    # value of the module global `_DB_ENGINE` variable. This is done in order to
    # - reuse the same database engine throughout the lifecycle of the application
    # - provide an opportunity to clear the cache when needed
    #
    # Note: this function cannot use the `functools.cache` decorator because
    # the `settings` parameter is not hashable
    global _DB_ENGINE
    if _DB_ENGINE is None:
        _DB_ENGINE = create_async_engine(db_dsn, echo=False)
    return _DB_ENGINE


def get_sync_engine(settings: SeisLabDataSettings) -> Engine:
    global _SYNC_DB_ENGINE
    if _SYNC_DB_ENGINE is None:
        _SYNC_DB_ENGINE = sqlmodel.create_engine(
            settings.database_dsn.unicode_string(),
            echo=settings.debug,
        )
    return _SYNC_DB_ENGINE


def get_session_maker(engine: AsyncEngine):
    return async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
