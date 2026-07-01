import asyncio
from collections.abc import AsyncGenerator

from .. import subscribers
from ..schemas import messages as message_schemas


async def handle_resource_modified(
    message: message_schemas.ResourceModificationMessage,
    context: subscribers.HandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    if message.succeeded:
        yield f"[green]Success:[/green] {message.resource_type.value} {message.resource_id!r} {message.modification.value}"
    else:
        yield f"[red]Error:[/red] {message.resource_type.value} {message.modification.value} failed with {message.details!r}"
    if done is not None:
        done.set()
