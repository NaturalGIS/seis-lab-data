import asyncio
import logging
from collections.abc import AsyncGenerator

from datastar_py.sse import DatastarEvent, ServerSentEventGenerator

from ... import subscribers
from ...schemas import messages as message_schemas
from .common import flash_ui_message_after_redirect

logger = logging.getLogger(__name__)


async def handle_new_page_survey_related_record_creation_successful(
    message: message_schemas.SurveyRelatedRecordCreatedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
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
