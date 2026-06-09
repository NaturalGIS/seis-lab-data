import asyncio
import dataclasses
import json
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

import typer
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from redis import asyncio as aioredis

from .. import (
    config,
    constants,
    operations,
    schemas,
    subscribers,
)
from ..db import queries
from ..errors import SeisLabDataError
from ..events.emitters import null_emitter
from ..schemas import identifiers
from ..processing import (
    broker,
    tasks,
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
    broker.setup_broker(settings)
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
    disable_event_emitter: bool = True,
):
    """Generate synthetic data"""
    created = []
    admin_ = ctx.obj["admin_user"]
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    emitter = (
        settings.get_event_emitter() if not disable_event_emitter else null_emitter
    )
    async with settings.get_db_session_maker()() as session:
        dataset_categories = await queries.collect_all_dataset_categories(session)
        workflow_stages = await queries.collect_all_workflow_stages(session)
        domain_types = await queries.collect_all_domain_types(session)
        project_generator = sampledata.generate_sample_projects(
            owners=[admin_],
            dataset_categories=[
                identifiers.DatasetCategoryId(dc.id) for dc in dataset_categories
            ],
            domain_types=[identifiers.DomainTypeId(dt.id) for dt in domain_types],
            workflow_stages=[
                identifiers.WorkflowStageId(ws.id) for ws in workflow_stages
            ],
        )
        for i in range(num_projects):
            ctx.obj["main"].status_console.print(
                f"Creating project {i + 1}/{num_projects}..."
            )
            project_to_create, missions_info = next(project_generator)
            created.append(
                await operations.create_project(
                    project_to_create,
                    initiator=admin_,
                    session=session,
                    event_emitter=emitter,
                )
            )
            for mission_index, (mission_to_create, records_to_create) in enumerate(
                missions_info
            ):
                ctx.obj["main"].status_console.print(
                    f"\tCreating mission ({mission_index + 1}/{len(missions_info)}) for project with {len(records_to_create)} records..."
                )
                await operations.create_survey_mission(
                    mission_to_create,
                    initiator=admin_,
                    session=session,
                    event_emitter=emitter,
                )
                for record_index, record_to_create in enumerate(records_to_create):
                    # ctx.obj["main"].status_console.print(
                    #     f"\t\tCreating record ({record_index + 1}/{len(records_to_create)}) for mission..."
                    # )
                    await operations.create_survey_related_record(
                        record_to_create,
                        initiator=admin_,
                        session=session,
                        event_emitter=emitter,
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
async def load_sample_projects_via_tasks(ctx: typer.Context):
    redis_client: aioredis.Redis = ctx.obj["main"].redis_client
    admin_ = ctx.obj["admin_user"]

    projects_to_create = list(sampledata.get_projects_to_create(owner=admin_))
    remaining = len(projects_to_create)

    async def handle_project_creation_started(
        message: subscribers.ProjectCreationStartedMessage,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        yield "Project creation has started"

    async def handle_project_creation_successful(
        message: subscribers.ProjectCreationSuccessfulMessage,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining
        yield f"Project {message.project_id!r} created successfully!"
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    async def handle_project_creation_failed(
        message: subscribers.ProjectCreationFailedMessage,
        done: asyncio.Event | None = None,
    ) -> AsyncGenerator[str, None]:
        nonlocal remaining
        yield f"Project creation failed with {message.details!r}"
        remaining -= 1
        if remaining == 0 and done is not None:
            done.set()

    subscription = subscribers.subscribe_to_topic(
        redis_client,
        topic_name=constants.NEW_TOPIC_PROJECTS,
        message_handlers={
            "project_creation_started": handle_project_creation_started,
            "project_creation_successful": handle_project_creation_successful,
            "project_creation_failed": handle_project_creation_failed,
        },
    )

    for to_create in projects_to_create:
        ctx.obj["main"].status_console.print(
            f"Queueing project {to_create.name.en!r} for creation..."
        )
        tasks.succinct_create_project.send(
            raw_to_create=to_create.model_dump_json(exclude_none=True),
            raw_initiator=json.dumps(dataclasses.asdict(admin_)),
        )  # noqa

    async for chunk in subscription:
        ctx.obj["main"].status_console.print(chunk)


@app.async_command()
async def load_sample_projects(ctx: typer.Context):
    """Load sample projects into the database."""
    created = []
    admin_ = ctx.obj["admin_user"]
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        for to_create in sampledata.get_projects_to_create(owner=admin_):
            ctx.obj["main"].status_console.print(
                f"Creating project {to_create.name.en!r}..."
            )
            try:
                created.append(
                    await operations.create_project(
                        to_create,
                        initiator=admin_,
                        session=session,
                        event_emitter=settings.get_event_emitter(),
                    )
                )
            except SeisLabDataError as err:
                ctx.obj["main"].status_console.print(f"[red]{err}[/red]")
                continue
            except IntegrityError as err:
                await session.rollback()
                if isinstance(err.orig, UniqueViolation):
                    ctx.obj["main"].status_console.print(
                        f"Project {to_create.id!r} already exists, skipping..."
                    )
                else:
                    raise RuntimeError from err
    for created_project in created:
        to_show = schemas.ProjectReadListItem(**created_project.model_dump())
        ctx.obj["main"].status_console.print(to_show)


@app.async_command()
async def load_sample_survey_missions(ctx: typer.Context):
    """Load sample survey missions into the database."""
    created = []
    admin_ = ctx.obj["admin_user"]
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        for to_create in sampledata.get_survey_missions_to_create(admin_):
            try:
                created.append(
                    await operations.create_survey_mission(
                        to_create,
                        initiator=admin_,
                        session=session,
                        event_emitter=settings.get_event_emitter(),
                    )
                )
            except IntegrityError as err:
                await session.rollback()
                if isinstance(err.orig, UniqueViolation):
                    ctx.obj["main"].status_console.print(
                        f"Survey mission {to_create.id!r} already exists, skipping..."
                    )
                else:
                    raise RuntimeError from err
    for created_survey_mission in created:
        to_show = schemas.SurveyMissionReadListItem.from_db_instance(
            created_survey_mission
        )
        ctx.obj["main"].status_console.print(to_show)


@app.async_command()
async def load_sample_survey_related_records(ctx: typer.Context):
    """Load sample survey-related records into the database."""
    created = []
    admin_ = ctx.obj["admin_user"]
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        all_dataset_categories = await queries.collect_all_dataset_categories(session)
        all_domain_types = await queries.collect_all_domain_types(session)
        all_workflow_stages = await queries.collect_all_workflow_stages(session)
        for to_create in sampledata.get_survey_related_records_to_create(
            owner=admin_,
            dataset_categories={c.name["en"]: c for c in all_dataset_categories},
            domain_types={d.name["en"]: d for d in all_domain_types},
            workflow_stages={w.name["en"]: w for w in all_workflow_stages},
        ):
            try:
                created.append(
                    await operations.create_survey_related_record(
                        to_create,
                        initiator=admin_,
                        session=session,
                        event_emitter=settings.get_event_emitter(),
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
        to_show = schemas.SurveyRelatedRecordReadListItem.from_db_instance(
            created_survey_record
        )
        ctx.obj["main"].status_console.print(to_show)
