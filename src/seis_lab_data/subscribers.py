import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import (
    Any,
    Annotated,
    Literal,
    Protocol,
    TypeVar,
    TypeAlias,
)

import pydantic
from redis.asyncio import Redis

from .schemas import identifiers

logger = logging.getLogger(__name__)


class ProjectCreationStartedMessage(pydantic.BaseModel):
    type: Literal["project_creation_started"] = "project_creation_started"


class ProjectCreationSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_creation_successful"] = "project_creation_successful"
    project_id: identifiers.ProjectId


class ProjectCreationFailedMessage(pydantic.BaseModel):
    type: Literal["project_creation_failed"] = "project_creation_failed"
    details: str


class HelloMessage(pydantic.BaseModel):
    type: Literal["hello"]
    greeting: str
    sleep_for_seconds: int = 1


SldPubSubMessage: TypeAlias = Annotated[
    ProjectCreationStartedMessage
    | ProjectCreationFailedMessage
    | ProjectCreationSuccessfulMessage
    | HelloMessage,
    pydantic.Field(discriminator="type"),
]
T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class MessageHandlerProtocol(Protocol[T_co]):
    def __call__(
        self,
        message: Any,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[T_co, None]:
        """Handle incoming messages and yield the result

        The ``done`` parameter can be used to signal to the caller that
        processing is finished, if needed.
        """
        ...


async def subscribe_to_topic(
    redis_client: Redis,
    topic_name: str,
    message_handlers: dict[str, MessageHandlerProtocol[T]],
) -> AsyncGenerator[T, None]:
    """
    Subscribe to a pubsub topic and dispatch incoming messages to relevant handlers.
    """
    done_event = asyncio.Event()
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(topic_name)
        try:
            async for message in pubsub.listen():
                if done_event.is_set():
                    break
                if message["type"] != "message":
                    continue

                try:
                    parsed = pydantic.TypeAdapter(SldPubSubMessage).validate_json(
                        message["data"]
                    )
                except pydantic.ValidationError as err:
                    logger.warning(err)
                    logger.warning(
                        f"Unrecognised message {message['data']!r} "
                        f"on {topic_name!r}, skipping"
                    )
                    continue

                handler = message_handlers.get(parsed.type)
                if handler is None:
                    logger.debug(f"No handler for {parsed.type!r}, ignoring")
                    continue

                async for chunk in handler(parsed, done=done_event):
                    yield chunk

                if done_event.is_set():
                    break

        except asyncio.CancelledError:
            logger.info(f"pubsub listener for {topic_name!r} cancelled")
        finally:
            await pubsub.unsubscribe(topic_name)


async def hello_handler(
    hello_message: HelloMessage, done: asyncio.Event | None = None
) -> AsyncGenerator[str, None]:
    """Example handler.

    You can test it interactively like this:

    ```
    python -m asyncio
    >>> import asyncio
    >>> import redis.asyncio as aioredis
    >>> from seis_lab_data import subscribers
    >>> from seis_lab_data.config import get_settings
    >>> from seis_lab_data.schemas.events import EventType
    >>> s = get_settings()
    >>> rc = aioredis.from_url(s.message_broker_dsn.unicode_string())
    >>> async for chunk in subscribers.subscribe_to_topic(
    ...     rc,
    ...     "demo-topic",
    ...     {"hello": subscribers.hello_handler}
    ... ):
    ```

    and in the redis-cli:

    ```
    PUBLISH demo-topic '{"type": "hello", "greeting": "hi", "sleep_for_seconds": 1}'
    ```
    """
    message = [
        "Hi there!",
        "How's life?",
        "I hope it is fine",
        "Mine is good",
        f"You sent me this greeting: {hello_message.greeting!r}",
        "Thanks for that, may you have it in double",
    ]
    for index, sentence in enumerate(message):
        yield sentence
        if index != len(message) - 1:
            await asyncio.sleep(hello_message.sleep_for_seconds)
    else:
        yield "About to leave"
    if done is not None:
        done.set()
