import dataclasses
import json
import asyncio
import logging
import time
from collections.abc import AsyncGenerator

from datastar_py.sse import ServerSentEventGenerator
from datastar_py.starlette import DatastarEvent

from ... import (
    constants,
    subscribers,
)
from ...schemas import (
    messages as message_schemas,
    webui as webui_schemas,
)
from ...tasks import (
    projects as project_tasks,
    surveymissions as mission_tasks,
    surveyrelatedrecords as record_tasks,
)

logger = logging.getLogger(__name__)


async def flash_ui_message_after_redirect(
    notification: webui_schemas.Notification,
) -> AsyncGenerator[DatastarEvent, None]:
    payload = {
        "message": notification.message,
        "category": {
            "success": "primary",
            "error": "danger",
        }.get(notification.category, "info"),
    }
    logger.debug(f"{payload=}")
    yield ServerSentEventGenerator.execute_script(
        f"localStorage.setItem('sld:flash', '{notification.model_dump_json(exclude_none=True)}');"
    )


async def flash_ui_message_same_page(
    notification: webui_schemas.Notification,
) -> AsyncGenerator[DatastarEvent, None]:
    yield ServerSentEventGenerator.execute_script(
        f"showFlash({notification.model_dump_json(exclude_none=True)})"
    )


async def handle_resource_modification_new_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    notification = None
    match context, message:
        case (
            subscribers.HandlerContext(
                target_page=constants.PageType.RESOURCE_NEW,
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            ),
            message_schemas.ResourceModificationMessage(
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            ),
        ):
            if (
                not message.succeeded
            ):  # only send notification if the context has the same request_id
                if context.request_id == message.request_id:
                    notification = webui_schemas.Notification(
                        message=f"{message.resource_type.capitalize()} could not be {message.modification}: {message.details}",
                        category="error",
                    )
            else:
                notification = webui_schemas.Notification(
                    message=f"{message.resource_type.capitalize()} was {message.modification} successfully!"
                )
        case _:
            ...
    if notification:
        async for event in flash_ui_message_after_redirect(notification):
            yield event
    match message.resource_type:
        case constants.ResourceType.ASSET_DISCOVERY_CONFIG:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("asset_discovery_configurations:list"))
            )
        case constants.ResourceType.CATEGORY:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("dataset_categories:list"))
            )
        case constants.ResourceType.WORKFLOW_STAGE:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("workflow_stages:list"))
            )
        case constants.ResourceType.PROJECT:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("projects:list"))
            )
        case constants.ResourceType.MISSION:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "projects:detail", project_id=message.parent_id
                    )
                )
            )
        case constants.ResourceType.RECORD:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_missions:detail", survey_mission_id=message.parent_id
                    )
                )
            )


async def handle_resource_modification_list_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    notification = None
    match context, message:
        case (
            subscribers.HandlerContext(
                target_page=constants.PageType.RESOURCE_LIST,
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            ),
            message_schemas.ResourceModificationMessage(
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            ),
        ):
            if (
                not message.succeeded
            ):  # only send notification if the context has the same request_id
                if context.request_id == message.request_id:
                    notification = webui_schemas.Notification(
                        message=f"{message.resource_type.capitalize()} could not be {message.modification}: {message.details}",
                        category="error",
                    )
            else:
                notification = webui_schemas.Notification(
                    message=f"{message.resource_type.capitalize()} was {message.modification} successfully!"
                )
        case _:
            ...
    if notification:
        async for event in flash_ui_message_same_page(notification):
            yield event
    # update datastar signal that frontend recognizes as needing to re-fetch listing
    yield ServerSentEventGenerator.patch_signals(
        {"listingVersion": int(time.time() * 1000)}
    )


async def handle_resource_modification_edit_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Enqueue validation and redirect to project detail page after editing."""
    logger.debug(f"{message=}")
    logger.debug(f"{context=}")
    if message.resource_id != context.resource_id:
        return

    match message.resource_type:
        case constants.ResourceType.PROJECT:
            project_tasks.validate_project.send(
                raw_request_id=str(message.request_id),
                raw_project_id=str(message.resource_id),
                raw_initiator=json.dumps(dataclasses.asdict(context.user)),
            )  # noqa
        case constants.ResourceType.MISSION:
            mission_tasks.validate_survey_mission.send(
                raw_request_id=str(message.request_id),
                raw_survey_mission_id=str(message.resource_id),
                raw_initiator=json.dumps(dataclasses.asdict(context.user)),
            )  # noqa
        case constants.ResourceType.RECORD:
            record_tasks.validate_survey_related_record.send(
                raw_request_id=str(message.request_id),
                raw_survey_related_record_id=str(message.resource_id),
                raw_initiator=json.dumps(dataclasses.asdict(context.user)),
            )  # noqa

    if message.succeeded:
        notification = webui_schemas.Notification(
            message=f"{message.resource_type.capitalize()} updated successfully!",
            category="success",
        )
    else:
        notification = webui_schemas.Notification(
            message=f"{message.resource_type.capitalize()} could not be updated: {message.details}",
            category="error",
        )

    async for event in flash_ui_message_after_redirect(notification):
        yield event

    match message.resource_type:
        case constants.ResourceType.PROJECT:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "projects:detail", project_id=message.resource_id
                    )
                )
            )
        case constants.ResourceType.MISSION:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_missions:detail", survey_mission_id=message.resource_id
                    )
                )
            )
        case constants.ResourceType.RECORD:
            yield ServerSentEventGenerator.redirect(
                str(
                    context.url_resolver(
                        "survey_related_records:detail",
                        survey_related_record_id=message.resource_id,
                    )
                )
            )
        case constants.ResourceType.ASSET_DISCOVERY_CONFIG:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("asset_discovery_configurations:list"))
            )
        case constants.ResourceType.CATEGORY:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("dataset_categories:list"))
            )
        case constants.ResourceType.WORKFLOW_STAGE:
            yield ServerSentEventGenerator.redirect(
                str(context.url_resolver("workflow_stages:list"))
            )


async def handle_resource_modification_detail_page(
    message: message_schemas.SldPubSubMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.resource_id != context.resource_id:
        return
    if not message.succeeded:  # if same request_id, show a notification
        if message.request_id == context.request_id:
            async for event in flash_ui_message_same_page(
                webui_schemas.Notification(
                    message=f"{message.resource_type.capitalize()} {message.modification} failed: {message.details}",
                    category="error",
                )
            ):
                yield event
    else:
        match message.modification:
            case constants.ResourceModification.DELETED:
                redirect_to = {
                    constants.ResourceType.PROJECT: "projects:list",
                    constants.ResourceType.MISSION: "survey_missions:list",
                    constants.ResourceType.RECORD: "survey_related_records:list",
                }.get(message.resource_type)
                async for event in flash_ui_message_after_redirect(
                    webui_schemas.Notification(
                        message=f"{message.resource_type.capitalize()} was deleted",
                    )
                ):
                    yield event
                if redirect_to:
                    yield ServerSentEventGenerator.redirect(
                        str(context.url_resolver(redirect_to))
                    )
