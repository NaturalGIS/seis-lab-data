import asyncio
import dataclasses
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import TypeAlias

from datastar_py.consts import ElementPatchMode
from datastar_py.sse import ServerSentEventGenerator
from datastar_py.starlette import DatastarEvent

from ...schemas import (
    messages as message_schemas,
    webui as webui_schemas,
)
from ...operations import projects as project_ops
from ...processing import projects as project_tasks
from ... import subscribers
from .common import (
    flash_ui_message_after_redirect,
    flash_ui_message_same_page,
)

logger = logging.getLogger(__name__)

ProjectModified: TypeAlias = (
    message_schemas.ProjectCreationSuccessfulMessage
    | message_schemas.ProjectDeletionSuccessfulMessage
    | message_schemas.ProjectUpdateSuccessfulMessage
    | message_schemas.ProjectCreatedMessage
    | message_schemas.ProjectUpdatedMessage
    | message_schemas.ProjectDeletedMessage
)


async def handle_new_page_project_creation_successful(
    message: message_schemas.ProjectCreationSuccessfulMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Enqueue validation and redirect to project detail page after creation."""
    if message.request_id != context.request_id:
        return

    project_tasks.validate_project.send(
        raw_project_id=str(message.project_id),
        raw_initiator=json.dumps(dataclasses.asdict(context.user)),
    )

    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            data_test_id="processing-success-message",
            status="success",
            message=f"project {message.project_id} created - you will be redirected shortly.",
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Project {message.project_id} created successfully!",
            "category": "success",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(context.url_resolver("projects:detail", project_id=message.project_id))
    )


async def handle_new_page_project_creation_failed(
    message: message_schemas.ProjectCreationFailedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.request_id != context.request_id:
        return
    raise NotImplementedError


async def handle_list_page_project_modification(
    message: ProjectModified,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    match message:
        case (
            message_schemas.ProjectDeletionSuccessfulMessage()
            | message_schemas.ProjectDeletedMessage()
        ):
            message = (
                f"Project {message.project_id} has been deleted - Reloaded project list"
            )
        case _:
            message = "Project list has changed - Reloaded projects"
    async for event in flash_ui_message_same_page(
        {
            "message": message,
            "category": "info",
        }
    ):
        yield event
    # update datastar signal that frontend recognizes as needing to re-fetch list of projects
    yield ServerSentEventGenerator.patch_signals(
        {"projectListingVersion": int(time.time() * 1000)}
    )


async def handle_edit_page_project_modification_failure(
    message: message_schemas.ProjectNotUpdatedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Redirect and show error"""
    if message.request_id != context.request_id:
        return

    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Project {message.project_id} failed to update - {message.details}",
            "category": "warning",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(context.url_resolver("projects:detail", project_id=message.project_id))
    )


async def handle_edit_page_project_modification_successful(
    message: message_schemas.ProjectUpdatedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Enqueue validation and redirect to project detail page after editing."""
    logger.info(f"{message=}")
    logger.info(f"{context=}")
    if message.project_id != context.project_id:
        return

    project_tasks.validate_project.send(
        raw_project_id=str(message.project_id),
        raw_initiator=json.dumps(dataclasses.asdict(context.user)),
    )

    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            data_test_id="processing-success-message",
            status="success",
            message=f"project {message.project_id} created - you will be redirected shortly.",
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Project {message.project_id} updated successfully!",
            "category": "success",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(context.url_resolver("projects:detail", project_id=message.project_id))
    )


async def handle_detail_page_project_deletion_success(
    message: message_schemas.ProjectDeletionSuccessfulMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Update a project's detail page when the project has been deleted successfully."""
    if message.project_id != context.project_id:
        return
    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            data_test_id="processing-success-message",
            status="success",
            message=f"project {message.project_id} deleted - you will be redirected shortly.",
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
    async for event in flash_ui_message_after_redirect(
        {
            "message": f"Project {message.project_id} deleted successfully!",
            "category": "success",
        }
    ):
        yield event
    yield ServerSentEventGenerator.redirect(str(context.url_resolver("projects:list")))


async def handle_detail_page_project_deletion_failure(
    message: message_schemas.ProjectDeletionFailedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Updates a project's detail page when the project deletion fails."""
    if message.project_id != context.project_id:
        return
    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            data_test_id="processing-failed-message",
            status="failure",
            message=f"Error: project {message.project_id} deletion failed - {message.details}",
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
    if done is not None:
        done.set()


async def handle_detail_page_project_discovery_started(
    message: message_schemas.ProjectDiscoveryStartedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Update project detail page when discovery starts."""
    if message.project_id != context.project_id:
        return
    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            data_test_id="processing-discovery-started-message",
            status="success",
            message="Project discovery started",
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
    if done is not None:
        done.set()


async def handle_detail_page_project_discovery_successful(
    message: message_schemas.ProjectDiscoverySuccessfulMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Update project detail page when discovery ends successfully."""
    if message.project_id != context.project_id:
        return
    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            data_test_id="processing-discovery-successful-message",
            status="success",
            message="Project discovery finished",
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
    if done is not None:
        done.set()


async def handle_detail_page_project_status_changed(
    message: message_schemas.ProjectStatusChangedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Update the status signal on the project detail page."""
    if message.project_id != context.project_id:
        return
    yield ServerSentEventGenerator.patch_signals({"status": message.new_status.value})


async def handle_detail_page_project_validated(
    message: message_schemas.ProjectValidatedMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Update the validation result on the project detail page."""
    if message.project_id != context.project_id:
        return
    if context.db_session_factory is not None:
        async with context.db_session_factory() as session:
            project = await project_ops.get_project(
                message.project_id, context.user, session
            )
        if project is not None:
            details_html = ""
            if not project.validation_result.get("is_valid"):
                details_html = "<ul>"
                for err in project.validation_result.get("errors") or []:
                    details_html += f"<li>{err['name']}: {err['message']}</li>"
                details_html += "</ul>"
            yield ServerSentEventGenerator.patch_elements(
                details_html,
                selector=webui_schemas.selector_info.validation_result_details_selector,
                mode=ElementPatchMode.INNER,
            )
    yield ServerSentEventGenerator.patch_signals({"isValid": message.is_valid})


async def handle_detail_page_project_discovery_progress(
    message: message_schemas.ProjectDiscoveryProgressMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Append a discovery progress message on the project detail page."""
    if message.project_id != context.project_id:
        return
    message_template = context.jinja_environment.get_template(
        "processing/progress-message-list-item.html"
    )
    yield ServerSentEventGenerator.patch_elements(
        message_template.render(
            status="info",
            message=message.details,
        ),
        selector=webui_schemas.selector_info.feedback_selector,
        mode=ElementPatchMode.APPEND,
    )
