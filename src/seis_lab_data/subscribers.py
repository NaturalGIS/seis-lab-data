import asyncio
import dataclasses
import logging
from collections.abc import AsyncGenerator
from typing import (
    Any,
    Callable,
    Protocol,
    TypeVar,
)

import jinja2
import pydantic
from redis.asyncio import Redis
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


# @dataclasses.dataclass(frozen=True)
# class AssetDiscoveryConfigurationHandlerContext(HandlerContext):
#     asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId | None = None
#
#
# @dataclasses.dataclass(frozen=True)
# class ProjectHandlerContext(HandlerContext):
#     project_id: identifiers.ProjectId | None = None
#
#
# @dataclasses.dataclass(frozen=True)
# class SurveyMissionHandlerContext(HandlerContext):
#     survey_mission_id: identifiers.SurveyMissionId | None = None
#
#
# @dataclasses.dataclass(frozen=True)
# class SurveyRelatedRecordHandlerContext(HandlerContext):
#     survey_related_record_id: identifiers.SurveyRelatedRecordId | None = None


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


# async def old_subscribe_to_topic[T, TContext: HandlerContext](
#     redis_client: Redis,
#     topic_name: str,
#     handler_context: TContext,
#     message_handlers: dict[str, MessageHandlerProtocol[T, TContext]],
# ) -> AsyncGenerator[T, None]:
#     """
#     Subscribe to a pubsub topic and dispatch incoming messages to relevant handlers.
#     """
#     done_event = asyncio.Event()
#     async with redis_client.pubsub() as pubsub:
#         await pubsub.subscribe(topic_name)
#         try:
#             async for message in pubsub.listen():
#                 if done_event.is_set():
#                     break
#                 if message["type"] != "message":
#                     continue
#
#                 try:
#                     parsed = pydantic.TypeAdapter(message_schemas.SldPubSubMessage).validate_json(
#                         message["data"]
#                     )
#                 except pydantic.ValidationError as err:
#                     logger.warning(err)
#                     logger.warning(
#                         f"Unrecognised message {message['data']!r} "
#                         f"on {topic_name!r}, skipping"
#                     )
#                     continue
#
#                 handler = message_handlers.get(parsed.type)
#                 if handler is None:
#                     logger.debug(f"No handler for {parsed.type!r}, ignoring")
#                     continue
#
#                 async for chunk in handler(
#                     parsed, context=handler_context, done=done_event
#                 ):
#                     yield chunk
#
#                 if done_event.is_set():
#                     break
#
#         except asyncio.CancelledError:
#             logger.info(f"pubsub listener for {topic_name!r} cancelled")
#         finally:
#             await pubsub.unsubscribe(topic_name)


async def subscribe_to_topic[T, TContext: HandlerContext](
    redis_client: Redis,
    topic_name: str,
    handler_context: TContext,
    message_handlers: dict[str, MessageHandlerProtocol[T, TContext]],
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
                    parsed = pydantic.TypeAdapter(
                        message_schemas.SldPubSubMessage
                    ).validate_json(message["data"])
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

                async for chunk in handler(
                    parsed, context=handler_context, done=done_event
                ):
                    yield chunk

                if done_event.is_set():
                    break

        except asyncio.CancelledError:
            logger.info(f"pubsub listener for {topic_name!r} cancelled")
        finally:
            await pubsub.unsubscribe(topic_name)
