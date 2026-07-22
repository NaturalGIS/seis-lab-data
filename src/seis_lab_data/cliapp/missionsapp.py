import asyncio
import dataclasses
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import typer
import redis.asyncio as aioredis

from .. import (
    config,
    constants,
    subscribers,
)
from ..operations import (
    projects as project_ops,
    surveymissions as mission_ops,
)
from ..tasks import (
    discovery as discovery_tasks,
)
from ..schemas import (
    common as common_schemas,
    identifiers,
    messages as message_schemas,
    surveymissions as mission_schemas,
)
from .asynctyper import AsyncTyper


app = AsyncTyper()


@app.callback()
def missions_app_callback(ctx: typer.Context):
    """Manage survey missions."""


@app.async_command(name="create")
async def create_survey_mission(
    ctx: typer.Context,
    parent_project_id: uuid.UUID,
    owner: str,
    name_en: str,
    name_pt: str,
    description_en: str,
    description_pt: str,
    relative_path: str,
    link: Annotated[list[dict], typer.Option(parser=json.loads)],
):
    """Create a new survey mission."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        if (
            project := await project_ops.get_project(
                identifiers.ProjectId(parent_project_id),
                ctx.obj["admin_user"],
                session,
            )
        ) is None:
            ctx.obj["main"].status_console.print(
                "Cannot create survey mission as the parent project does not exist."
            )
            raise typer.Abort()
        created = await mission_ops.create_survey_mission(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_create=mission_schemas.SurveyMissionCreate(
                id=identifiers.SurveyMissionId(uuid.uuid4()),
                project_id=identifiers.ProjectId(project.id),
                owner_id=identifiers.UserId(owner),
                name=common_schemas.LocalizableDraftName(en=name_en, pt=name_pt),
                description=common_schemas.LocalizableDraftDescription(
                    en=description_en, pt=description_pt
                ),
                relative_path=relative_path,
                links=[common_schemas.LinkSchema(**li) for li in link],
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        print(mission_schemas.SurveyMissionReadDetail(**created.model_dump()))


@app.async_command(name="list")
async def list_survey_missions(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List survey missions."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        items, num_total = await mission_ops.list_survey_missions(
            session,
            initiator=ctx.obj["admin_user"],
            limit=limit,
            offset=offset,
            include_total=True,
        )
    print(f"Total records: {num_total}")
    for item in items:
        print(mission_schemas.SurveyMissionReadListItem(**item.model_dump()))


@app.async_command(name="get")
async def get_survey_mission(ctx: typer.Context, survey_mission_id: uuid.UUID):
    """Get details about a survey mission"""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        survey_mission = await mission_ops.get_survey_mission(
            identifiers.SurveyMissionId(survey_mission_id),
            ctx.obj["admin_user"].id,
            session,
        )
        if survey_mission is None:
            print(f"Survey mission {survey_mission_id!r} not found")
        else:
            print(
                mission_schemas.SurveyMissionReadDetail.from_db_instance(
                    survey_mission
                ).model_dump_json()
            )


@app.async_command(name="delete")
async def delete_survey_mission(
    ctx: typer.Context,
    survey_mission_id: uuid.UUID,
):
    """Delete a survey mission."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await mission_ops.delete_survey_mission(
            request_id=identifiers.RequestId(uuid.uuid4()),
            survey_mission_id=identifiers.SurveyMissionId(survey_mission_id),
            initiator=ctx.obj["admin_user"].id,
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted survey mission with id {survey_mission_id!r}")


@app.async_command(name="discover-contents")
async def discover_survey_mission_contents(
    ctx: typer.Context,
    survey_mission_id: uuid.UUID,
):
    """Discover contents of a survey mission automatically."""
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client

    async def handle_message(
        message: message_schemas.DiscoveryMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        if context.request_id != message.request_id:
            return

        match message:
            case message_schemas.DiscoveryMessage(succeeded=False):
                yield f"[red]Error:[/red] Mission discovery failed with {message.details!r}"
                done.set()
            case message_schemas.DiscoveryMessage(succeeded=True):
                yield f"[green]Success:[/green] Mission {message.resource_id!r} discovery completed successfully!"
                done.set()

    topic_names = [constants.NEW_TOPIC_SURVEY_MISSIONS]
    pubsub = await subscribers.open_topic_subscription(redis_client, topic_names)
    discovery_tasks.discover_survey_mission_contents.send(
        raw_request_id=str(uuid.uuid4()),
        raw_survey_mission_id=str(survey_mission_id),
        raw_initiator=json.dumps(dataclasses.asdict(ctx.obj["admin_user"])),
    )  # noqa
    subscription = subscribers.iter_topic_messages(
        pubsub,
        topic_names,
        subscribers.HandlerContext(resource_id=str(survey_mission_id)),
        {"discovery": handle_message},
    )
    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)
