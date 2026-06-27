import asyncio
from collections.abc import AsyncGenerator

from .. import subscribers
from ..schemas import messages as message_schemas


async def handle_project_deletion_success(
    message: message_schemas.ProjectDeletedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    yield f"[green]Success:[/green] Project {message.project_id!r} deleted successfully!"
    if done is not None:
        done.set()


async def handle_project_deletion_failure(
    message: message_schemas.ProjectNotDeletedMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    yield f"[red]Error:[/red] Project deletion failed with {message.details!r}"
    if done is not None:
        done.set()
