import logging
from typing import Protocol

from redis import asyncio as aioredis

from .schemas import (
    events,
    messages,
)

logger = logging.getLogger(__name__)


class EventDispatcherProtocol(Protocol):
    async def __call__(self, event: events.SeisLabDataEvent) -> None: ...


async def no_op_dispatcher(event: events.SeisLabDataEvent) -> None:
    logger.debug(f"no-op dispatch called with {event=}")


class RedisEventDispatcher:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def __call__(self, event: events.SeisLabDataEvent) -> None:
        logger.debug(f"received event {event=}")
        match event:
            case events.ResourceModificationEvent():
                await self._redis.publish(
                    channel=event.resource_type.get_topic_name(),
                    message=messages.ResourceModificationMessage(
                        resource_type=event.resource_type,
                        request_id=event.request_id,
                        resource_id=event.resource_id,
                        parent_resource_id=event.parent_resource_id,
                        modification=event.modification,
                        succeeded=event.succeeded,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ResourceStatusChangedEvent():
                await self._redis.publish(
                    channel=event.resource_type.get_topic_name(),
                    message=messages.ResourceStatusChangedMessage(
                        resource_type=event.resource_type,
                        resource_id=event.resource_id,
                        succeeded=event.succeeded,
                        new_status=event.new_status,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.DiscoveryEvent():
                await self._redis.publish(
                    channel=event.resource_type.get_topic_name(),
                    message=messages.DiscoveryMessage(
                        resource_type=event.resource_type,
                        resource_id=event.resource_id,
                        request_id=event.request_id,
                        modification=event.modification,
                        succeeded=event.succeeded,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ValidationEvent():
                await self._redis.publish(
                    channel=event.resource_type.get_topic_name(),
                    message=messages.ValidationMessage(
                        resource_type=event.resource_type,
                        resource_id=event.resource_id,
                        request_id=event.request_id,
                        modification=event.modification,
                        succeeded=event.succeeded,
                        is_valid=event.is_valid,
                        details=event.details,
                    ).model_dump_json(),
                )
            case _:
                logger.debug(f"no Redis dispatch configured for {event=}")
