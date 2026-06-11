import asyncio
import json
from collections.abc import AsyncGenerator

from datastar_py.starlette import DatastarEvent
from datastar_py.consts import ElementPatchMode
from datastar_py.sse import ServerSentEventGenerator

from .. import subscribers
from ..schemas import (
    messages as message_schemas,
    webui as webui_schemas,
)


async def handle_project_deletion_list_page(
    message: message_schemas.ProjectDeletionSuccessfulMessage,
    context: subscribers.ProjectHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Update the project list page when a project has been deleted."""
    #  produce the project list again and yield it - need the pagination and filters that are active
    raise NotImplementedError


async def handle_project_deletion_success_detail_page(
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
    result_feedback = {
        "message": f"Project {message.project_id} deleted successfully!",
        "category": "success",
    }
    yield ServerSentEventGenerator.execute_script(
        f"localStorage.setItem('sld:flash', '{json.dumps(result_feedback)}');"
    )
    yield ServerSentEventGenerator.redirect(str(context.url_resolver("projects:list")))


async def handle_project_deletion_failure_detail_page(
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
