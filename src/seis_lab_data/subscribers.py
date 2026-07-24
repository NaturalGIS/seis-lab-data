import asyncio
import dataclasses
import logging
from collections.abc import AsyncGenerator
from typing import (
    Any,
    Callable,
    Protocol,
    Sequence,
    TypeVar,
)

import jinja2
import pydantic
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from sqlalchemy.ext.asyncio.session import async_sessionmaker

from . import constants
from .schemas import (
    identifiers,
    messages as message_schemas,
    user as user_schemas,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


@dataclasses.dataclass(frozen=True)
class HandlerContext:
    jinja_environment: jinja2.Environment | None = None
    url_resolver: Callable[[str], Any] | None = None
    db_session_factory: async_sessionmaker | None = None
    user: user_schemas.User | None = None
    request_id: identifiers.RequestId | None = None
    target_page: constants.PageType | None = None
    resource_type: constants.ResourceType | None = None
    resource_id: str | None = None


class MessageHandlerProtocol[T_co, TContext: HandlerContext](Protocol):
    def __call__(
        self,
        message: Any,
        context: TContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[T_co, None]:
        """Handle incoming messages and yield the result

        The ``done`` parameter can be used to signal to the caller that
        processing is finished, if needed.
        """
        ...


async def open_topic_subscription(
    redis_client: Redis,
    topic_names: Sequence[str],
) -> PubSub:
    """Subscribe to a pubsub topic and return once the subscription is live.

    Callers must await this *before* dispatching any messages that are
    expected to trigger a `resource_modified` event on this topic - otherwise
    a fast consumer can publish before anyone is listening and the event is
    lost for good (redis pub/sub is fire-and-forget).
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(*topic_names)
    logger.debug(f"Subscribed to {topic_names}")
    return pubsub


async def iter_topic_messages[T, TContext: HandlerContext](
    pubsub: PubSub,
    topic_names: Sequence[str],
    handler_context: TContext,
    message_handlers: dict[str, MessageHandlerProtocol[T, TContext]],
) -> AsyncGenerator[T, None]:
    """
    Dispatch incoming messages on an already-subscribed pubsub to relevant handlers.
    """
    done_event = asyncio.Event()
    try:
        async for message in pubsub.listen():
            if done_event.is_set():
                break
            if message["type"] != "message":
                continue

            try:
                parsed = pydantic.TypeAdapter(
                    message_schemas.SldPubSubMessage
                ).validate_json(message["data"])
            except pydantic.ValidationError as err:
                logger.warning(err)
                logger.warning(
                    f"Unrecognised message {message['data']!r} "
                    f"on {topic_names!r}, skipping"
                )
                continue

            handler = message_handlers.get(parsed.type)
            if handler is None:
                logger.debug(f"No handler for {parsed.type!r}, ignoring")
                continue

            async for chunk in handler(
                parsed, context=handler_context, done=done_event
            ):
                yield chunk

            if done_event.is_set():
                break

    except asyncio.CancelledError:
        logger.info(f"pubsub listener for {topic_names!r} cancelled")
    finally:
        await pubsub.unsubscribe(*topic_names)
        await pubsub.aclose()
