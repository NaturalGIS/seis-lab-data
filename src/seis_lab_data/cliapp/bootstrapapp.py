import asyncio
import dataclasses
import json

import uuid
from anyio import Path
from collections.abc import AsyncGenerator

import typer
from redis import asyncio as aioredis

from .. import (
    config,
    constants,
    subscribers,
)
from ..schemas import (
    identifiers,
    messages as message_schemas,
)
from ..tasks import (
    datasetcategories as category_tasks,
    discovery as discovery_tasks,
    workflowstages as stage_tasks,
)
from . import utils
from .asynctyper import AsyncTyper

app = AsyncTyper()


@app.callback()
def bootstrap_app_callback(
    ctx: typer.Context,
    admin_username: str | None = typer.Option(
        default="akadmin",
        help="Authentik username of the admin user to act as.",
    ),
    admin_user_id: str | None = typer.Option(
        default=None,
        help=(
            "Authentik sub (UUID) of the admin user to act as. Takes "
            "precedence over --admin-username."
        ),
    ),
):
    """Bootstrapp newly installed instances."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    ctx.obj["admin_user"] = asyncio.run(
        utils.resolve_admin_user(settings, admin_username, admin_user_id)
    )


@app.async_command(name="all")
async def bootstrap_all(ctx: typer.Context):
    """Create all default data."""
    await ctx.invoke(bootstrap_dataset_categories, ctx=ctx)
    await ctx.invoke(bootstrap_workflow_stages, ctx=ctx)
    await ctx.invoke(bootstrap_asset_discovery_configurations, ctx=ctx)


@app.async_command(name="asset-discovery-configurations")
async def bootstrap_asset_discovery_configurations(ctx: typer.Context):
    """Create default asset discovery configurations."""
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]
    bootstrap_data = await utils.get_bootstrap_data(
        Path(__file__).parent / "bootstrapdata.toml"
    )
    to_create = bootstrap_data.get(constants.ResourceType.ASSET_DISCOVERY_CONFIG, [])
    remaining = len(to_create)

    async def handle_message(
        message: message_schemas.ResourceModificationMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining

        if message.request_id != context.request_id:
            return

        notification_message = (
            (
                f"[green]Success:[/green] "
                f"{constants.ResourceType.ASSET_DISCOVERY_CONFIG.value.upper()} "
                f"{message.resource_id!r} {message.modification.value} successfully!"
            )
            if message.succeeded
            else (
                f"[red]Error:[/red] "
                f"{constants.ResourceType.ASSET_DISCOVERY_CONFIG.value.upper()} "
                f"{message.modification.value} failed with {message.details!r}"
            )
        )

        yield notification_message
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    request_id = identifiers.RequestId(uuid.uuid4())
    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_names=[constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS],
        handler_context=subscribers.HandlerContext(
            request_id=request_id,
        ),
        message_handlers={"resource_modified": handle_message},
    )

    for current in to_create:
        ctx.obj["main"].status_console.print(f"Queueing {current.name} for creation...")
        discovery_tasks.create_asset_discovery_configuration.send(
            raw_request_id=str(request_id),
            raw_to_create=current.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)


@app.async_command(name="workflow-stages")
async def bootstrap_workflow_stages(
    ctx: typer.Context,
):
    """Create default workflow stages.

    These are read from the input TOML file.
    """
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]

    bootstrap_data = await utils.get_bootstrap_data(
        Path(__file__).parent / "bootstrapdata.toml"
    )
    to_create = bootstrap_data.get(constants.ResourceType.WORKFLOW_STAGE, [])
    remaining = len(to_create)

    async def handle_message(
        message: message_schemas.ResourceModificationMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining

        if message.request_id != context.request_id:
            return

        notification_text = (
            (
                f"[green]Success:[/green] {message.resource_type.value.upper()} "
                f"{message.resource_id!r} {message.modification.value} successfully!"
            )
            if message.succeeded
            else (
                f"[red]Error:[/red] {message.resource_type.value.upper()} "
                f"{message.modification.value} failed with {message.details!r}"
            )
        )
        yield notification_text
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    request_id = identifiers.RequestId(uuid.uuid4())
    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_names=[constants.NEW_TOPIC_WORKFLOW_STAGES],
        handler_context=subscribers.HandlerContext(
            request_id=request_id,
        ),
        message_handlers={"resource_modified": handle_message},
    )

    for current in to_create:
        ctx.obj["main"].status_console.print(
            f"Queueing {current.name.en!r} for creation..."
        )
        stage_tasks.create_workflow_stage.send(
            raw_request_id=str(request_id),
            raw_to_create=current.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)


@app.async_command(name="dataset-categories")
async def bootstrap_dataset_categories(
    ctx: typer.Context,
):
    """Create default dataset categories.

    These are read from the input TOML file.
    """
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]

    bootstrap_data = await utils.get_bootstrap_data(
        Path(__file__).parent / "bootstrapdata.toml"
    )
    to_create = bootstrap_data.get(constants.ResourceType.CATEGORY, [])
    remaining = len(to_create)

    async def handle_message(
        message: message_schemas.ResourceModificationMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining

        if message.request_id != context.request_id:
            return

        notification_text = (
            (
                f"[green]Success:[/green] {message.resource_type.value.upper()} "
                f"{message.resource_id!r} {message.modification.value} successfully!"
            )
            if message.succeeded
            else (
                f"[red]Error:[/red] {message.resource_type.value.upper()} "
                f"{message.modification.value} failed with {message.details!r}"
            )
        )
        yield notification_text
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    request_id = identifiers.RequestId(uuid.uuid4())
    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_names=[constants.NEW_TOPIC_DATASET_CATEGORIES],
        handler_context=subscribers.HandlerContext(
            request_id=request_id,
        ),
        message_handlers={"resource_modified": handle_message},
    )

    for current in to_create:
        ctx.obj["main"].status_console.print(
            f"Queueing {current.name.en!r} for creation..."
        )
        category_tasks.create_dataset_category.send(
            raw_request_id=str(request_id),
            raw_to_create=current.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)
