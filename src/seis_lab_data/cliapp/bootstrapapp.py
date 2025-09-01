import uuid

import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    events,
    operations,
    schemas,
)
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
    categories_to_create = [
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("1ad54ca0-a28b-46c0-9776-3c9b7f3bc990"),
            name={"en": "bathymetry", "pt": "batimetria"},
        ),
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("3002d462-3f2e-4957-a56e-97175f91883a"),
            name={"en": "backscatter", "pt": "backscatter"},
        ),
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("53ec7259-5fbe-48d7-9d1b-508225add0a0"),
            name={"en": "seismic", "pt": "sísmica"},
        ),
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("333073eb-adc9-4ac7-b822-44f4df5575a3"),
            name={"en": "magnetometer/gradiometer", "pt": "magnetómetro/gradiómetro"},
        ),
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("4b17a645-dc10-488c-ba7d-47ff052efdf8"),
            name={
                "en": "superficial sediment samples",
                "pt": "amostras sedimento superficiais",
            },
        ),
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("fd68accf-057e-4813-b47a-aa4df3741c45"),
            name={"en": "cores", "pt": "núcleos"},
        ),
        schemas.DatasetCategoryCreate(
            id=uuid.UUID("43507846-a6cf-4e54-bd80-9ef5be334cf0"),
            name={"en": "CPT tests", "pt": "tests CPT"},
        ),
    ]
    created = []
    settings = ctx.obj["main"].settings
    async with ctx.obj["session_maker"]() as session:
        for to_create in categories_to_create:
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
    domain_types_to_create = [
        schemas.DomainTypeCreate(
            id=uuid.UUID("b06335e1-e8c2-4d27-9b20-5c3530fd4576"),
            name={"en": "geophysical", "pt": "geofísica"},
        ),
        schemas.DomainTypeCreate(
            id=uuid.UUID("474a9110-b8d5-4269-91a7-d8a307bd01c2"),
            name={"en": "geotechnical", "pt": "geotécnica"},
        ),
    ]
    created = []
    settings = ctx.obj["main"].settings
    async with ctx.obj["session_maker"]() as session:
        for to_create in domain_types_to_create:
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
    workflow_stages_to_create = [
        schemas.WorkflowStageCreate(
            id=uuid.UUID("ac51aa07-90e9-43d4-83b9-d079482a001e"),
            name={"en": "raw data", "pt": "dados brutos"},
        ),
        schemas.WorkflowStageCreate(
            id=uuid.UUID("6dc042b3-16f9-4a9a-a30a-ac9201b4eb1d"),
            name={"en": "quality control data", "pt": "dados controlo de qualidade"},
        ),
        schemas.WorkflowStageCreate(
            id=uuid.UUID("372ac9ed-c7b9-4be3-9030-30149f0b4295"),
            name={"en": "processed data", "pt": "dados processados"},
        ),
        schemas.WorkflowStageCreate(
            id=uuid.UUID("342fb236-6622-495e-ae6c-fd90f5cf0d16"),
            name={"en": "interpreted data", "pt": "dados interpretados"},
        ),
    ]
    created = []
    settings = ctx.obj["main"].settings
    async with ctx.obj["session_maker"]() as session:
        for to_create in workflow_stages_to_create:
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
