import json
import uuid
from typing import Annotated

import typer

from .. import (
    events,
    operations,
    schemas,
)
from .asynctyper import AsyncTyper

app = AsyncTyper()
projects_app = AsyncTyper()
dataset_categories_app = AsyncTyper()
domain_types_app = AsyncTyper()
workflow_stages_app = AsyncTyper()
app.add_typer(projects_app, name="projects")
app.add_typer(dataset_categories_app, name="dataset-categories")
app.add_typer(domain_types_app, name="domain-types")
app.add_typer(workflow_stages_app, name="workflow-stages")


def parse_json_links(raw_json: str):
    return json.loads(raw_json)


@app.callback()
def app_callback(ctx: typer.Context):
    """Manage system data."""


@projects_app.callback()
def projects_app_callback(ctx: typer.Context):
    """Manage projects."""


@projects_app.async_command(name="create")
async def create_project(
    ctx: typer.Context,
    owner: str,
    name_en: str,
    name_pt: str,
    description_en: str,
    description_pt: str,
    root_path: str,
    link: Annotated[list[dict], typer.Option(parser=parse_json_links)],
):
    """Create a new project."""
    async with ctx.obj["session_maker"]() as session:
        created = await operations.create_project(
            to_create=schemas.ProjectCreate(
                id=uuid.uuid4(),
                owner=owner,
                name={"en": name_en, "pt": name_pt},
                description={"en": description_en, "pt": description_pt},
                root_path=root_path,
                links=link,
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
        ctx.obj["main"].status_console.print(
            schemas.ProjectReadDetail(**created.model_dump())
        )


@projects_app.async_command(name="list")
async def list_projects(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List projects."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        items, num_total = await operations.list_projects(
            session,
            initiator=ctx.obj["admin_user"],
            limit=limit,
            offset=offset,
            include_total=True,
        )
    printer(f"Total records: {num_total}")
    for item in items:
        printer(schemas.ProjectReadListItem(**item.model_dump()))


@projects_app.async_command(name="delete")
async def delete_project(
    ctx: typer.Context,
    project_id: uuid.UUID,
):
    """Delete a project."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        await operations.delete_project(
            project_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
    printer(f"Deleted project with id {project_id!r}")


@dataset_categories_app.callback()
def dataset_categories_app_callback(ctx: typer.Context):
    """Manage dataset categories."""


@dataset_categories_app.async_command(name="create")
async def create_dataset_category(
    ctx: typer.Context,
    name_en: str,
    name_pt: str,
):
    """Create a new dataset category."""
    async with ctx.obj["session_maker"]() as session:
        created = await operations.create_dataset_category(
            to_create=schemas.DatasetCategoryCreate(
                id=uuid.uuid4(),
                name={"en": name_en, "pt": name_pt},
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
        ctx.obj["main"].status_console.print(
            schemas.DatasetCategoryRead(**created.model_dump())
        )


@dataset_categories_app.async_command(name="list")
async def list_dataset_categories(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List dataset categories."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        items, num_total = await operations.list_dataset_categories(
            session, limit=limit, offset=offset, include_total=True
        )
    printer(f"Total records: {num_total}")
    for item in items:
        printer(schemas.DatasetCategoryRead(**item.model_dump()))


@dataset_categories_app.async_command(name="delete")
async def delete_dataset_category(
    ctx: typer.Context,
    dataset_category_id: uuid.UUID,
):
    """Delete a dataset category."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        await operations.delete_dataset_category(
            dataset_category_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
    printer(f"Deleted dataset category with id {dataset_category_id!r}")


@domain_types_app.callback()
def domain_types_app_callback(ctx: typer.Context):
    """Manage domain types."""


@domain_types_app.async_command(name="create")
async def create_domain_type(
    ctx: typer.Context,
    name_en: str,
    name_pt: str,
):
    """Create a new domain type."""
    async with ctx.obj["session_maker"]() as session:
        created = await operations.create_domain_type(
            to_create=schemas.DomainTypeCreate(
                id=uuid.uuid4(),
                name={"en": name_en, "pt": name_pt},
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
        ctx.obj["main"].status_console.print(
            schemas.DomainTypeRead(**created.model_dump())
        )


@domain_types_app.async_command(name="list")
async def list_domain_types(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List domain types."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        items, num_total = await operations.list_domain_types(
            session, limit=limit, offset=offset, include_total=True
        )
    printer(f"Total records: {num_total}")
    for item in items:
        printer(schemas.DomainTypeRead(**item.model_dump()))


@domain_types_app.async_command(name="delete")
async def delete_domain_type(
    ctx: typer.Context,
    domain_type_id: uuid.UUID,
):
    """Delete a domain type."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        await operations.delete_domain_type(
            domain_type_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
    printer(f"Deleted domain type with id {domain_type_id!r}")


@workflow_stages_app.callback()
def workflow_stages_app_callback(ctx: typer.Context):
    """Manage workflow stages."""


@workflow_stages_app.async_command(name="create")
async def create_workflow_stage(
    ctx: typer.Context,
    name_en: str,
    name_pt: str,
):
    """Create a new workflow stage."""
    async with ctx.obj["session_maker"]() as session:
        created = await operations.create_workflow_stage(
            to_create=schemas.WorkflowStageCreate(
                id=uuid.uuid4(),
                name={"en": name_en, "pt": name_pt},
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
        ctx.obj["main"].status_console.print(
            schemas.WorkflowStageRead(**created.model_dump())
        )


@workflow_stages_app.async_command(name="list")
async def list_workflow_stages(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List workflow stages."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        items, num_total = await operations.list_workflow_stages(
            session, limit=limit, offset=offset, include_total=True
        )
    printer(f"Total records: {num_total}")
    for item in items:
        printer(schemas.WorkflowStageRead(**item.model_dump()))


@workflow_stages_app.async_command(name="delete")
async def delete_workflow_stage(
    ctx: typer.Context,
    workflow_stage_id: uuid.UUID,
):
    """Delete a workflow stage."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        await operations.delete_workflow_stage(
            workflow_stage_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
    printer(f"Deleted workflow stage with id {workflow_stage_id!r}")
