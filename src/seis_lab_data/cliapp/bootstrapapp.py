import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    events,
    operations,
    schemas,
)
from . import bootstrapdata
from .asynctyper import AsyncTyper

app = AsyncTyper()


@app.callback()
def bootstrap_app_callback(ctx: typer.Context):
    """Bootstrapp newly installed instances."""


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
    settings = ctx.obj["main"].settings
    async with ctx.obj["session_maker"]() as session:
        for to_create in bootstrapdata.DATASET_CATEGORIES_TO_CREATE.values():
            try:
                created.append(
                    await operations.create_dataset_category(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
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
    settings = ctx.obj["main"].settings
    async with ctx.obj["session_maker"]() as session:
        for to_create in bootstrapdata.DOMAIN_TYPES_TO_CREATE.values():
            try:
                created.append(
                    await operations.create_domain_type(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
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
    settings = ctx.obj["main"].settings
    async with ctx.obj["session_maker"]() as session:
        for to_create in bootstrapdata.WORKFLOW_STAGES_TO_CREATE.values():
            try:
                created.append(
                    await operations.create_workflow_stage(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
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
