import asyncio
import dataclasses
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import shapely
import typer
import redis.asyncio as aioredis

from .. import (
    config,
    constants,
    subscribers,
)
from ..operations import projects as project_ops
from ..tasks import (
    discovery as discovery_tasks,
    projects as project_tasks,
)
from ..schemas import (
    common as common_schemas,
    identifiers,
    messages as message_schemas,
    projects as project_schemas,
)
from .asynctyper import AsyncTyper
from . import handlers


app = AsyncTyper()


@app.callback()
def projects_app_callback(ctx: typer.Context):
    """Manage projects."""


def _parse_bbox_bounds(raw_bounds: str) -> shapely.Polygon:
    bounds = [float(coord) for coord in raw_bounds.split(",")]
    if len(bounds) != 4:
        raise ValueError("Bounds must have exactly four comma-separated values.")
    min_lon, min_lat, max_lon, max_lat = bounds
    return shapely.box(min_lon, min_lat, max_lon, max_lat)


@app.async_command(name="create")
async def create_project(
    ctx: typer.Context,
    owner: str,
    name_en: str,
    root_path: str,
    link: Annotated[list[dict], typer.Option(parser=json.loads)] = None,
    name_pt: str | None = None,
    description_en: str | None = None,
    description_pt: str | None = None,
    bbox_4326: Annotated[
        shapely.Polygon,
        typer.Option(
            parser=_parse_bbox_bounds,
            help=(
                "Bounds of the bounding box as a comma-separated list of "
                "min_lon,min_lat,max_lon,max_lat"
            ),
        ),
    ] = None,
):
    """Create a new project."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        created = await project_ops.create_project(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_create=project_schemas.ProjectCreate(
                id=identifiers.ProjectId(uuid.uuid4()),
                owner_id=identifiers.UserId(owner),
                name=common_schemas.LocalizableDraftName(en=name_en, pt=name_pt),
                description=common_schemas.LocalizableDraftDescription(
                    en=description_en, pt=description_pt
                ),
                root_path=root_path,
                bbox_4326=bbox_4326.wkt,
                links=[
                    common_schemas.LinkSchema(
                        url=li["url"],
                        link_description=common_schemas.LocalizableDraftDescription(
                            en=li.get("link_description", {}).get("en", ""),
                            pt=li.get("link_description", {}).get("pt", ""),
                        ),
                        media_type=li["media_type"],
                        relation=li["relation"],
                    )
                    for li in link or []
                ],
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        print(project_schemas.ProjectReadDetail(**created.model_dump()))


@app.async_command(name="get")
async def get_project(ctx: typer.Context, project_id: uuid.UUID):
    """Get details about a project"""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        project = await project_ops.get_project(
            identifiers.ProjectId(project_id),
            ctx.obj["admin_user"].id,
            session,
        )
        if project is None:
            print(f"Project {project_id!r} not found")
        else:
            print(
                project_schemas.ProjectReadDetail.from_db_instance(
                    project
                ).model_dump_json()
            )


@app.async_command(name="list")
async def list_projects(
    ctx: typer.Context,
    page: int = 1,
    page_size: int = 20,
):
    """List projects."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        items, num_total = await project_ops.list_projects(
            session,
            initiator=ctx.obj["admin_user"],
            page=page,
            page_size=page_size,
            include_total=True,
        )
    print(f"Total records: {num_total}")
    for item in items:
        print(project_schemas.ProjectReadListItem(**item.model_dump()))


@app.async_command(name="delete")
async def delete_project(
    ctx: typer.Context,
    project_id: uuid.UUID,
):
    """Delete a project."""
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_name=constants.NEW_TOPIC_PROJECTS,
        handler_context=subscribers.HandlerContext(),
        message_handlers={
            "project_deleted": handlers.handle_project_deletion_success,
            "project_not_deleted": handlers.handle_project_deletion_failure,
        },
    )
    project_tasks.delete_project.send(
        raw_request_id=str(uuid.uuid4()),
        raw_project_id=str(identifiers.ProjectId(project_id)),
        raw_initiator=json.dumps(dataclasses.asdict(ctx.obj["admin_user"])),
    )  # noqa
    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)


@app.async_command(name="old-delete")
async def old_delete_project(
    ctx: typer.Context,
    project_id: uuid.UUID,
):
    """Delete a project."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await project_ops.delete_project(
            request_id=identifiers.RequestId(uuid.uuid4()),
            project_id=identifiers.ProjectId(project_id),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted project with id {project_id!r}")


@app.async_command(name="discover-contents")
async def discover_project_contents(
    ctx: typer.Context,
    project_id: uuid.UUID,
):
    """Discover contents of a project automatically."""
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client

    async def handle_progress(
        message: message_schemas.ProjectDiscoveryProgressMessage,
        context: subscribers.ProjectHandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        yield f"[blue]Progress:[/blue] {message.details}"

    async def handle_success(
        message: message_schemas.ProjectDiscoverySucceededMessage,
        context: subscribers.ProjectHandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        yield f"[green]Success:[/green] Project {message.project_id!r} discovery completed successfully!"
        done.set()

    async def handle_failure(
        message: message_schemas.ProjectDiscoveryFailedMessage,
        context: subscribers.ProjectHandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        yield f"[red]Error:[/red] Project discovery failed with {message.details!r}"
        done.set()

    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_name=constants.NEW_TOPIC_PROJECTS,
        handler_context=subscribers.ProjectHandlerContext(
            project_id=identifiers.ProjectId(project_id)
        ),
        message_handlers={
            "project_discovery_progress": handle_progress,
            "project_discovery_successful": handle_success,
            "project_discovery_failed": handle_failure,
        },
    )
    discovery_tasks.discover_project_contents.send(
        raw_request_id=str(uuid.uuid4()),
        raw_project_id=str(identifiers.ProjectId(project_id)),
        raw_initiator=json.dumps(dataclasses.asdict(ctx.obj["admin_user"])),
    )  # noqa
    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)
