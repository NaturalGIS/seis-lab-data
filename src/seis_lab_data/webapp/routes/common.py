import asyncio
import dataclasses
import json
import logging
import uuid
from typing import (
    AsyncGenerator,
    Callable,
    Type,
    TypeVar,
)

import pydantic
from datastar_py import ServerSentEventGenerator
from datastar_py.consts import ElementPatchMode
from datastar_py.sse import DatastarEvent
from jinja2 import Template
from redis.asyncio import Redis
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.templating import Jinja2Templates

from ... import schemas
from ...constants import ProcessingStatus

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PaginationInfo:
    current_page: int
    page_size: int
    total_filtered_items: int
    total_unfiltered_items: int
    total_filtered_pages: int
    total_unfiltered_pages: int
    next_page: int | None
    previous_page: int | None
    collection_url: str
    next_page_url: str | None
    previous_page_url: str | None


@pydantic.validate_call
def get_pagination_info(
    current_page: pydantic.NonNegativeInt,
    page_size: pydantic.PositiveInt,
    total_filtered_items: pydantic.NonNegativeInt,
    total_unfiltered_items: pydantic.NonNegativeInt,
    collection_url: str,
) -> PaginationInfo:
    total_filtered_pages = get_page_count(total_filtered_items, page_size)
    total_unfiltered_pages = get_page_count(total_unfiltered_items, page_size)
    next_page = current_page + 1 if current_page < total_filtered_pages else None
    previous_page = current_page - 1 if current_page > 0 else None
    return PaginationInfo(
        current_page=current_page,
        page_size=page_size,
        total_filtered_items=total_filtered_items,
        total_unfiltered_items=total_unfiltered_items,
        total_filtered_pages=total_filtered_pages,
        total_unfiltered_pages=total_unfiltered_pages,
        next_page=next_page,
        previous_page=previous_page,
        collection_url=collection_url,
        next_page_url=f"{collection_url}?page={next_page}" if next_page else None,
        previous_page_url=(
            f"{collection_url}?page={previous_page}" if previous_page else None
        ),
    )


RequestPathRetrievableIdType = TypeVar(
    "RequestPathRetrievableIdType",
    schemas.ProjectId,
    schemas.SurveyMissionId,
    schemas.SurveyRelatedRecordId,
)


def get_id_from_request_path[RequestPathRetrievableIdType](
    request: Request, path_param_name: str, id_type: Type[RequestPathRetrievableIdType]
) -> RequestPathRetrievableIdType:
    try:
        return id_type(uuid.UUID(request.path_params[path_param_name]))
    except ValueError as err:
        raise HTTPException(400, f"Invalid ID format for {id_type.__name__}") from err


def get_page_from_request_params(
    request: Request,
    query_param_name: str = "page",
) -> int:
    try:
        current_page = int(request.query_params.get(query_param_name, 1))
        if current_page < 1:
            raise ValueError
        return current_page
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid page number")


@pydantic.validate_call
def get_page_count(
    total_items: pydantic.NonNegativeInt, page_size: pydantic.PositiveInt
) -> int:
    return (total_items + page_size - 1) // page_size


async def produce_event_stream_for_item_updates_topic(
    redis_client: Redis,
    request: Request,
    topic_name: str,
    on_message: Callable[[dict], AsyncGenerator[DatastarEvent, None]],
    timeout_seconds: int = 30,
):
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(topic_name)
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"client disconnected from topic {topic_name!r}")
                    break
                try:
                    if message := await pubsub.get_message(
                        ignore_subscribe_messages=False, timeout=timeout_seconds
                    ):
                        if message["type"] == "subscribe":
                            logger.debug(f"Subscribed to topic {topic_name!r}")
                        elif message["type"] == "message":
                            logger.debug(f"received message: {message=}")
                            async for datastar_event in on_message(message["data"]):
                                yield datastar_event
                    else:
                        logging.info(
                            f"pubsub listener for topic {topic_name!r} timed out after {timeout_seconds} seconds"
                        )
                        break
                except asyncio.CancelledError:
                    logger.info(
                        f"pubsub listener for topic {topic_name!r} was cancelled"
                    )
                    raise
        finally:
            await pubsub.unsubscribe(topic_name)


async def produce_event_stream_for_topic(
    redis_client: Redis,
    request: Request,
    topic_name: str,
    on_success: Callable[
        [schemas.ProcessingMessage, Template], AsyncGenerator[DatastarEvent, None]
    ],
    on_failure: Callable[
        [schemas.ProcessingMessage, Template], AsyncGenerator[DatastarEvent, None]
    ],
    patch_elements_selector: str,
    timeout_seconds: int = 30,
):
    template_processor: Jinja2Templates = request.state.templates
    message_template = template_processor.get_template(
        "processing/progress-message-list-item.html"
    )
    async with redis_client.pubsub() as pubsub:
        await pubsub.subscribe(topic_name)
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"client disconnected from topic {topic_name!r}")
                    break
                try:
                    if message := await pubsub.get_message(
                        ignore_subscribe_messages=False, timeout=timeout_seconds
                    ):
                        if message["type"] == "subscribe":
                            logger.debug(f"Subscribed to topic {topic_name!r}")
                        elif message["type"] == "message":
                            processing_message = schemas.ProcessingMessage(
                                **json.loads(message["data"])
                            )
                            logger.debug(f"Received message: {processing_message!r}")
                            if processing_message.status in (
                                ProcessingStatus.SUCCESS,
                                ProcessingStatus.FAILED,
                            ):
                                if (
                                    processing_message.status
                                    == ProcessingStatus.SUCCESS
                                ):
                                    async for datastar_event in on_success(
                                        processing_message, message_template
                                    ):
                                        yield datastar_event
                                else:
                                    async for datastar_event in on_failure(
                                        processing_message, message_template
                                    ):
                                        yield datastar_event
                                break
                            else:
                                yield ServerSentEventGenerator.patch_elements(
                                    message_template.render(
                                        status=processing_message.status,
                                        message=processing_message.message,
                                    ),
                                    selector=patch_elements_selector,
                                    mode=ElementPatchMode.APPEND,
                                )
                    else:
                        logging.info(
                            f"pubsub listener for topic {topic_name!r} timed out after {timeout_seconds} seconds"
                        )
                        break
                except asyncio.CancelledError:
                    logger.info(
                        f"pubsub listener for topic {topic_name!r} was cancelled"
                    )
                    raise
        finally:
            await pubsub.unsubscribe(topic_name)
