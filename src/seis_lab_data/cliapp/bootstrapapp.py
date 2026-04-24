import asyncio

import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    config,
    operations,
    schemas,
)
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
    await ctx.invoke(bootstrap_domain_types, ctx=ctx)
    await ctx.invoke(bootstrap_workflow_stages, ctx=ctx)


@app.async_command(name="dataset-categories")
async def bootstrap_dataset_categories(ctx: typer.Context):
    """Create default dataset categories."""
    created = []
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        for to_create in bootstrapdata.DATASET_CATEGORIES_TO_CREATE.values():
            try:
                created.append(
                    await operations.create_dataset_category(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        event_emitter=settings.get_event_emitter(),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Dataset category {to_create.name['en']!r} already exists, skipping..."
                )
                await session.rollback()
    for created_category in created:
        to_show = schemas.DatasetCategoryRead(**created_category.model_dump())
        ctx.obj["main"].status_console.print(to_show)


@app.async_command(name="domain-types")
async def bootstrap_domain_types(ctx: typer.Context):
    """Create default domain types."""
    created = []
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        for to_create in bootstrapdata.DOMAIN_TYPES_TO_CREATE.values():
            try:
                created.append(
                    await operations.create_domain_type(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        event_emitter=settings.get_event_emitter(),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Domain type {to_create.name['en']!r} already exists, skipping..."
                )
                await session.rollback()
    for created_domain_type in created:
        to_show = schemas.DomainTypeRead(**created_domain_type.model_dump())
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
                    await operations.create_workflow_stage(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        event_emitter=settings.get_event_emitter(),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Workflow stage {to_create.name['en']!r} already exists, skipping..."
                )
                await session.rollback()
    for created_workflow_stage in created:
        to_show = schemas.WorkflowStageRead(**created_workflow_stage.model_dump())
        ctx.obj["main"].status_console.print(to_show)
