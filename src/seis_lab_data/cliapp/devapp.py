import asyncio
import dataclasses
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import typer
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from redis import asyncio as aioredis

from .. import (
    config,
    constants,
    subscribers,
)
from ..operations import (
    projects as project_ops,
    surveymissions as mission_ops,
    surveyrelatedrecords as record_ops,
)
from ..db.queries import (
    datasetcategories as category_queries,
    workflowstages as stage_queries,
)
from ..dispatch import no_op_dispatcher
from ..schemas import (
    identifiers,
    messages as message_schemas,
    surveyrelatedrecords as record_schemas,
)
from ..tasks import (
    projects as project_tasks,
    surveymissions as mission_tasks,
)
from . import sampledata
from .asynctyper import AsyncTyper
from .utils import resolve_admin_user

logger = logging.getLogger(__name__)
app = AsyncTyper()


@app.callback()
def dev_app_callback(
    ctx: typer.Context,
    admin_username: str | None = typer.Option(
        default="akadmin",
        help="Authentik username of the admin user to act as.",
    ),
    admin_user_id: str | None = typer.Option(
        default=None,
        help="Authentik sub (UUID) of the admin user to act as. Takes precedence over --admin-username.",
    ),
):
    """Dev-related commands"""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    ctx.obj["admin_user"] = asyncio.run(
        resolve_admin_user(settings, admin_username, admin_user_id)
    )


@app.async_command()
async def generate_many_projects(
    ctx: typer.Context,
    num_projects: Annotated[
        int,
        typer.Option(
            help=(
                "Number of projects to generate. Beware - the bigger this number, the longer this command "
                "will take to run"
            ),
            min=1,
            max=100,
        ),
    ] = 10,
    disable_event_dispatcher: bool = True,
):
    """Generate synthetic data"""
    created = []
    admin_ = ctx.obj["admin_user"]
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    emitter = (
        settings.get_event_dispatcher()
        if not disable_event_dispatcher
        else no_op_dispatcher
    )
    async with settings.get_db_session_maker()() as session:
        dataset_categories = await category_queries.collect_all_dataset_categories(
            session
        )
        workflow_stages = await stage_queries.collect_all_workflow_stages(session)
        project_generator = sampledata.generate_sample_projects(
            owners=[admin_],
            dataset_categories=[
                identifiers.DatasetCategoryId(dc.id) for dc in dataset_categories
            ],
            workflow_stages=[
                identifiers.WorkflowStageId(ws.id) for ws in workflow_stages
            ],
        )
        for i in range(num_projects):
            ctx.obj["main"].status_console.print(
                f"Creating project {i + 1}/{num_projects}..."
            )
            project_to_create, missions_info = next(project_generator)
            request_id = identifiers.RequestId(uuid.uuid4())
            created.append(
                await project_ops.create_project(
                    request_id=request_id,
                    to_create=project_to_create,
                    initiator=admin_,
                    session=session,
                    event_dispatcher=emitter,
                )
            )
            for mission_index, (mission_to_create, records_to_create) in enumerate(
                missions_info
            ):
                ctx.obj["main"].status_console.print(
                    f"\tCreating mission ({mission_index + 1}/{len(missions_info)}) for project with {len(records_to_create)} records..."
                )
                await mission_ops.create_survey_mission(
                    request_id=request_id,
                    to_create=mission_to_create,
                    initiator=admin_,
                    session=session,
                    event_dispatcher=emitter,
                )
                for record_index, record_to_create in enumerate(records_to_create):
                    await record_ops.create_survey_related_record(
                        request_id=request_id,
                        to_create=record_to_create,
                        initiator=admin_,
                        session=session,
                        event_dispatcher=emitter,
                    )
            ctx.obj["main"].status_console.print("--------")
        ctx.obj["main"].status_console.print("Done!")


@app.async_command()
async def load_all_samples(ctx: typer.Context):
    """Load all sample data into the database."""
    await ctx.invoke(load_sample_projects, ctx=ctx)
    await ctx.invoke(load_sample_survey_missions, ctx=ctx)
    await ctx.invoke(load_sample_survey_related_records, ctx=ctx)


@app.async_command()
async def load_sample_projects(ctx: typer.Context):
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]

    projects_to_create = list(sampledata.get_projects_to_create(owner=admin_))
    remaining = len(projects_to_create)

    async def handle_message(
        message: message_schemas.ResourceModificationMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining
        if message.request_id != context.request_id:
            return
        if message.succeeded:
            yield f"[green]Success:[/green] Project {message.resource_id!r} created successfully!"
        else:
            yield f"[red]Error:[/red] Project creation failed with {message.details!r}"
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    request_id = identifiers.RequestId(uuid.uuid4())
    topic_names = [constants.NEW_TOPIC_PROJECTS]
    pubsub = await subscribers.open_topic_subscription(redis_client, topic_names)

    for to_create in projects_to_create:
        ctx.obj["main"].status_console.print(
            f"Queueing project {to_create.name.en!r} for creation..."
        )
        project_tasks.create_project.send(
            raw_request_id=str(request_id),
            raw_to_create=to_create.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    subscription = subscribers.iter_topic_messages(
        pubsub,
        topic_names,
        subscribers.HandlerContext(request_id=request_id),
        {"resource_modified": handle_message},
    )
    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)


@app.async_command()
async def load_sample_survey_missions(ctx: typer.Context):
    """Load sample survey missions into the database."""
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]

    missions_to_create = list(sampledata.get_survey_missions_to_create(owner=admin_))
    remaining = len(missions_to_create)

    async def handle_message(
        message: message_schemas.ResourceModificationMessage,
        context: subscribers.HandlerContext,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining
        if message.request_id != context.request_id:
            return
        if message.succeeded:
            yield f"[green]Success:[/green] {message.resource_type.value} {message.resource_id!r} {message.modification.value} successfully!"
        else:
            yield f"[red]Error:[/red] {message.resource_type.value} {message.modification.value} failed with {message.details!r}"
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    request_id = identifiers.RequestId(uuid.uuid4())
    topic_names = [constants.NEW_TOPIC_SURVEY_MISSIONS]
    pubsub = await subscribers.open_topic_subscription(redis_client, topic_names)

    for to_create in missions_to_create:
        ctx.obj["main"].status_console.print(
            f"Queueing survey mission {to_create.name.en!r} for creation..."
        )
        mission_tasks.create_survey_mission.send(
            raw_request_id=str(request_id),
            raw_to_create=to_create.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    subscription = subscribers.iter_topic_messages(
        pubsub,
        topic_names,
        subscribers.HandlerContext(request_id=request_id),
        {"resource_modified": handle_message},
    )
    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)


@app.async_command()
async def load_sample_survey_related_records(ctx: typer.Context):
    """Load sample survey-related records into the database."""
    created = []
    admin_ = ctx.obj["admin_user"]
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        all_dataset_categories = await category_queries.collect_all_dataset_categories(
            session
        )
        all_workflow_stages = await stage_queries.collect_all_workflow_stages(session)
        for to_create in sampledata.get_survey_related_records_to_create(
            owner=admin_,
            dataset_categories={c.name["en"]: c for c in all_dataset_categories},
            workflow_stages={w.name["en"]: w for w in all_workflow_stages},
        ):
            try:
                created.append(
                    await record_ops.create_survey_related_record(
                        request_id=identifiers.RequestId(uuid.uuid4()),
                        to_create=to_create,
                        initiator=admin_,
                        session=session,
                        event_dispatcher=settings.get_event_dispatcher(),
                    )
                )
            except IntegrityError as err:
                await session.rollback()
                if isinstance(err.orig, UniqueViolation):
                    ctx.obj["main"].status_console.print(
                        f"Survey-related record {to_create.id!r} already exists, skipping..."
                    )
                else:
                    raise RuntimeError from err
    for created_survey_record in created:
        to_show = record_schemas.SurveyRelatedRecordReadListItem.from_db_instance(
            created_survey_record
        )
        ctx.obj["main"].status_console.print(to_show)
