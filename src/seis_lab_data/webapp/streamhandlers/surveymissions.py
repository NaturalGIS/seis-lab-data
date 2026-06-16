import asyncio
import logging
from collections.abc import AsyncGenerator

from datastar_py.sse import DatastarEvent, ServerSentEventGenerator

from ... import subscribers
from ...schemas import messages as message_schemas
from .common import flash_ui_message_after_redirect

logger = logging.getLogger(__name__)


async def handle_new_page_survey_mission_created(
    message: message_schemas.SurveyMissionCreatedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.request_id != context.request_id:
        return
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Survey mission {message.survey_mission_id} created successfully!",
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


async def handle_detail_page_survey_mission_deleted(
    message: message_schemas.SurveyMissionDeletedMessage,
    context: subscribers.SurveyMissionHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.survey_mission_id != context.survey_mission_id:
        return
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Survey mission {message.survey_mission_id} deleted successfully!",
            "category": "success",
        }
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
    context: subscribers.SurveyMissionHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.survey_mission_id != context.survey_mission_id:
        return
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Survey mission {message.survey_mission_id} updated successfully!",
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
