import asyncio
import dataclasses
import json
import uuid
from collections.abc import AsyncGenerator

import typer
from redis import asyncio as aioredis
from sqlalchemy.exc import IntegrityError

from .. import (
    config,
    constants,
    subscribers,
)
from ..operations import surveyrelatedrecords as record_ops
from ..schemas import (
    identifiers,
    messages as message_schemas,
    surveyrelatedrecords as record_schemas,
)
from ..tasks import discovery as discovery_tasks
from . import bootstrapdata
from .asynctyper import AsyncTyper
from .utils import resolve_admin_user

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
        resolve_admin_user(settings, admin_username, admin_user_id)
    )


@app.async_command(name="all")
async def bootstrap_all(ctx: typer.Context):
    """Create all default data."""
    await ctx.invoke(bootstrap_dataset_categories, ctx=ctx)
    await ctx.invoke(bootstrap_workflow_stages, ctx=ctx)


@app.async_command(name="asset-discovery-configurations")
async def bootstrap_asset_discovery_configurations(ctx: typer.Context):
    """Create default asset discovery configurations."""
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]

    remaining = len(bootstrapdata.ASSET_DISCOVERY_CONFIGURATIONS_TO_CREATE)

    async def handle_message(
        message: message_schemas.ResourceModificationMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining

        if message.request_id != context.request_id:
            return

        if message.succeeded:
            yield f"[green]Success:[/green] Asset discovery configuration {message.resource_id!r} created successfully!"
            remaining -= 1
            if remaining == 0 and done is not None:
                done.set()
        else:
            yield f"[red]Error:[/red] Asset discovery configuration creation failed with {message.details!r}"
            remaining -= 1
            if remaining == 0 and done is not None:
                done.set()

    request_id = identifiers.RequestId(uuid.uuid4())
    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_name=constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
        handler_context=subscribers.HandlerContext(
            request_id=request_id,
        ),
        message_handlers={"resource_modified": handle_message},
    )

    for to_create in bootstrapdata.ASSET_DISCOVERY_CONFIGURATIONS_TO_CREATE.values():
        ctx.obj["main"].status_console.print(
            f"Queueing asset_discovery_configuration {to_create.name!r} for creation..."
        )
        discovery_tasks.create_asset_discovery_configuration.send(
            raw_request_id=str(request_id),
            raw_to_create=to_create.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)

    # created = []
    # settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    # async with settings.get_db_session_maker()() as session:
    #     for to_create in bootstrapdata.ASSET_DISCOVERY_CONFIGURATIONS_TO_CREATE.values():
    #         try:
    #             created.append(
    #                 await discovery_ops.create_asset_discovery_configuration(
    #                     request_id=identifiers.RequestId(uuid.uuid4()),
    #                     to_create=to_create,
    #                     initiator=ctx.obj["admin_user"],
    #                     session=session,
    #                     event_dispatcher=settings.get_event_dispatcher(),
    #                 )
    #             )
    #         except IntegrityError as err:
    #             ctx.obj["main"].status_console.print(
    #                 f"Asset discovery configuration could not be created: {str(err)}"
    #             )
    #             await session.rollback()
    # for created_item in created:
    #     to_show = discovery_schemas.AssetDiscoveryReadDetail.model_validate(created_item, from_attributes=True)
    #     ctx.obj["main"].status_console.print(to_show)


@app.async_command(name="dataset-categories")
async def bootstrap_dataset_categories(ctx: typer.Context):
    """Create default dataset categories."""
    created = []
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        for to_create in bootstrapdata.DATASET_CATEGORIES_TO_CREATE.values():
            try:
                created.append(
                    await record_ops.create_dataset_category(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        event_dispatcher=settings.get_event_dispatcher(),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Dataset category {to_create.name['en']!r} already exists, skipping..."
                )
                await session.rollback()
    for created_category in created:
        to_show = record_schemas.DatasetCategoryRead(**created_category.model_dump())
        ctx.obj["main"].status_console.print(to_show)


@app.async_command(name="workflow-stages")
async def bootstrap_workflow_stages(ctx: typer.Context):
    """Create default workflow stages."""
    created = []
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        for to_create in bootstrapdata.WORKFLOW_STAGES_TO_CREATE.values():
            try:
                created.append(
                    await record_ops.create_workflow_stage(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        event_dispatcher=settings.get_event_dispatcher(),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Workflow stage {to_create.name['en']!r} already exists, skipping..."
                )
                await session.rollback()
    for created_workflow_stage in created:
        to_show = record_schemas.WorkflowStageRead(
            **created_workflow_stage.model_dump()
        )
        ctx.obj["main"].status_console.print(to_show)
