import asyncio
import logging
import time
from collections.abc import AsyncGenerator

from datastar_py.sse import DatastarEvent, ServerSentEventGenerator

from ... import subscribers
from ...schemas import (
    messages as message_schemas,
    webui as webui_schemas,
)
from .common import (
    flash_ui_message_after_redirect,
    flash_ui_message_same_page,
)

logger = logging.getLogger(__name__)


async def handle_new_page_survey_mission_created(
    message: message_schemas.SurveyMissionCreatedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.request_id != context.request_id:
        return
    async for event in flash_ui_message_after_redirect(
        webui_schemas.Notification(
            message=f"Survey mission {message.survey_mission_id} created successfully!",
            category="success",
        )
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


async def handle_detail_page_survey_mission_deleted(
    message: message_schemas.SurveyMissionDeletedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.survey_mission_id != context.resource_id:
        return
    async for event in flash_ui_message_after_redirect(
        webui_schemas.Notification(
            message=f"Survey mission {message.survey_mission_id} deleted successfully!",
            category="success",
        )
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(
            context.url_resolver(
                "projects:detail",
                project_id=message.project_id,
            )
        )
    )


async def handle_edit_page_survey_mission_updated(
    message: message_schemas.SurveyMissionUpdatedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.survey_mission_id != context.resource_id:
        return
    async for event in flash_ui_message_after_redirect(
        webui_schemas.Notification(
            message=f"Survey mission {message.survey_mission_id} updated successfully!",
            category="success",
        )
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


async def handle_list_page_survey_mission_modification(
    message: (
        message_schemas.SurveyMissionCreatedMessage
        | message_schemas.SurveyMissionUpdatedMessage
        | message_schemas.SurveyMissionDeletedMessage
    ),
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    match message:
        case message_schemas.SurveyMissionDeletedMessage():
            message = f"Survey mission {message.survey_mission_id} has been deleted - Reloaded list"
        case _:
            message = "Survey mission list has changed - Reloaded list"
    async for event in flash_ui_message_same_page(
        webui_schemas.Notification(message=message)
    ):
        yield event
    # update datastar signal that frontend recognizes as needing to re-fetch list of survey missions
    yield ServerSentEventGenerator.patch_signals(
        {"recordListingVersion": int(time.time() * 1000)}
    )
