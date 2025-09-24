from functools import wraps
from typing import Callable

import dramatiq

from .middleware import (
    AsyncSqlAlchemyDbMiddleware,
    AsyncRedisPubSubMiddleware,
    SeisLabDataSettingsMiddleware,
)


def redis_client(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        broker: dramatiq.Broker = dramatiq.get_broker()
        for middleware in broker.middleware:
            if isinstance(middleware, AsyncRedisPubSubMiddleware):
                return await func(*args, **kwargs, redis_client=middleware.redis_client)
        else:
            raise RuntimeError("No AsyncRedisPubSubMiddleware found in the broker")

    return wrapper


def sld_settings(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        broker: dramatiq.Broker = dramatiq.get_broker()
        for middleware in broker.middleware:
            if isinstance(middleware, SeisLabDataSettingsMiddleware):
                return await func(*args, **kwargs, settings=middleware.sld_settings)
        else:
            raise RuntimeError("No SeisLabDataSettingsMiddleware found in the broker")

    return wrapper


def session_maker(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        broker: dramatiq.Broker = dramatiq.get_broker()
        for middleware in broker.middleware:
            if isinstance(middleware, AsyncSqlAlchemyDbMiddleware):
                return await func(
                    *args, **kwargs, session_maker=middleware.session_maker
                )
        else:
            raise RuntimeError("No AsyncSqlAlchemyDbMiddleware found in the broker")

    return wrapper
