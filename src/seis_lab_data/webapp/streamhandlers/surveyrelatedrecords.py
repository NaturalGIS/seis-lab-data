import asyncio
import logging
import time
from collections.abc import AsyncGenerator

from datastar_py.sse import DatastarEvent, ServerSentEventGenerator

from ... import subscribers
from ...schemas import messages as message_schemas
from .common import (
    flash_ui_message_after_redirect,
    flash_ui_message_same_page,
)

logger = logging.getLogger(__name__)


async def handle_new_page_record_created(
    message: message_schemas.SurveyRelatedRecordCreatedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    logger.info(f"{locals()=}")
    if message.request_id != context.request_id:
        return
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Survey-related record {message.record_id} created successfully!",
            "category": "success",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(
            context.url_resolver(
                "survey_related_records:detail",
                survey_related_record_id=message.record_id,
            )
        )
    )


async def handle_detail_page_record_deleted(
    message: message_schemas.SurveyRelatedRecordDeletedMessage,
    context: subscribers.SurveyRelatedRecordHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.record_id != context.survey_related_record_id:
        return
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Survey-related record {message.record_id} deleted successfully!",
            "category": "success",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(
            context.url_resolver(
                "survey_missions:detail",
                survey_mission_id=message.survey_mission_id,
            )
        )
    )


async def handle_edit_page_survey_record_updated(
    message: message_schemas.SurveyRelatedRecordUpdatedMessage,
    context: subscribers.SurveyRelatedRecordHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.record_id != context.survey_related_record_id:
        return
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Survey-related record {message.record_id} updated successfully!",
            "category": "success",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(
            context.url_resolver(
                "survey_related_records:detail",
                survey_related_record_id=message.record_id,
            )
        )
    )


async def handle_list_page_record_modification(
    message: (
        message_schemas.SurveyRelatedRecordCreatedMessage
        | message_schemas.SurveyRelatedRecordUpdatedMessage
        | message_schemas.SurveyRelatedRecordDeletedMessage
    ),
    context: subscribers.SurveyRelatedRecordHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    match message:
        case message_schemas.SurveyRelatedRecordDeletedMessage():
            message = f"Survey-related record {message.record_id} has been deleted - Reloaded record list"
        case _:
            message = "Record list has changed - Reloaded records"
    async for event in flash_ui_message_same_page(
        {
            "message": message,
            "category": "info",
        }
    ):
        yield event
    # update datastar signal that frontend recognizes as needing to re-fetch list of records
    yield ServerSentEventGenerator.patch_signals(
        {"recordListingVersion": int(time.time() * 1000)}
    )
