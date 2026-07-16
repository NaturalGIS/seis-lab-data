import asyncio
import time
from collections.abc import AsyncGenerator
from typing import TypeAlias

from datastar_py.sse import ServerSentEventGenerator
from datastar_py.starlette import DatastarEvent

from ... import subscribers
from ...schemas import (
    messages as message_schemas,
    webui as webui_schemas,
)
from .common import (
    flash_ui_message_same_page,
    flash_ui_message_after_redirect,
)

AssetDiscoveryConfigurationModified: TypeAlias = (
    message_schemas.AssetDiscoveryConfigurationCreatedMessage
    | message_schemas.AssetDiscoveryConfigurationUpdatedMessage
    | message_schemas.AssetDiscoveryConfigurationDeletedMessage
)

AssetDiscoveryConfigurationNotModified: TypeAlias = (
    message_schemas.AssetDiscoveryConfigurationNotCreatedMessage
    | message_schemas.AssetDiscoveryConfigurationNotUpdatedMessage
    | message_schemas.AssetDiscoveryConfigurationNotDeletedMessage
)


async def handle_list_page_asset_discovery_configuration_modification(
    message: AssetDiscoveryConfigurationModified,
    context: subscribers.AssetDiscoveryConfigurationHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    match message:
        case message_schemas.AssetDiscoveryConfigurationDeletedMessage():
            message = f"Asset discovery configuration {message.asset_discovery_configuration_id} has been deleted - Reloaded listing"
        case _:
            message = "Asset discovery configuration list has changed"
    async for event in flash_ui_message_same_page(
        webui_schemas.Notification(message=message)
    ):
        yield event
    # update datastar signal that frontend recognizes as needing to re-fetch listing
    yield ServerSentEventGenerator.patch_signals(
        {"listingVersion": int(time.time() * 1000)}
    )


async def handle_new_page_asset_discovery_configuration_creation_successful(
    message: message_schemas.AssetDiscoveryConfigurationCreatedMessage,
    context: subscribers.AssetDiscoveryConfigurationHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    """Redirect to detail page after creation."""
    if message.request_id != context.request_id:
        return

    async for event in flash_ui_message_after_redirect(
        webui_schemas.Notification(
            message=f"Asset discovery configuration {message.asset_discovery_configuration_id} created successfully!",
            category="success",
        )
    ):
        yield event
    yield ServerSentEventGenerator.redirect(
        str(
            context.url_resolver(
                "asset_discovery_configurations:list",
            )
        )
    )


async def handle_new_page_asset_discovery_configuration_creation_failed(
    message: message_schemas.AssetDiscoveryConfigurationNotCreatedMessage,
    context: subscribers.AssetDiscoveryConfigurationHandlerContext,
    done: asyncio.Event | None = None,
) -> AsyncGenerator[DatastarEvent, None]:
    if message.request_id != context.request_id:
        return
    raise NotImplementedError
