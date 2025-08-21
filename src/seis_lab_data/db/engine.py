from sqlalchemy.ext.asyncio import create_async_engine

from ..config import SeisLabDataSettings

_DB_ENGINE = None


def get_engine(settings: SeisLabDataSettings):
    # This function implements caching of the sqlalchemy engine, relying on the
    # value of the module global `_DB_ENGINE` variable. This is done in order to
    # - reuse the same database engine throughout the lifecycle of the application
    # - provide an opportunity to clear the cache when needed
    #
    # Note: this function cannot use the `functools.cache` decorator because
    # the `settings` parameter is not hashable
    global _DB_ENGINE
    if _DB_ENGINE is None:
        _DB_ENGINE = create_async_engine(settings.database_url, echo=settings.debug)
    return _DB_ENGINE
