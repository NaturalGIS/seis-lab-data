from typing import Annotated

import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    events,
    operations,
    schemas,
)
from ..db import queries
from ..events.emitters import null_emitter
from . import sampledata
from .asynctyper import AsyncTyper

app = AsyncTyper()


@app.callback()
def dev_app_callback(ctx: typer.Context):
    """Dev-related commands"""


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
    enable_event_emitter: bool = False,
):
    """Generate synthetic data"""
    session_maker = ctx.obj["session_maker"]
    created = []
    settings = ctx.obj["main"].settings
    emitter = (
        events.get_event_emitter(settings) if enable_event_emitter else null_emitter
    )
    async with session_maker() as session:
        dataset_categories = await queries.collect_all_dataset_categories(session)
        workflow_stages = await queries.collect_all_workflow_stages(session)
        domain_types = await queries.collect_all_domain_types(session)
        project_generator = sampledata.generate_sample_projects(
            owners=[schemas.UserId("fake_user")],
            dataset_categories=[
                schemas.DatasetCategoryId(dc.id) for dc in dataset_categories
            ],
            domain_types=[schemas.DomainTypeId(dt.id) for dt in domain_types],
            workflow_stages=[schemas.WorkflowStageId(ws.id) for ws in workflow_stages],
        )
        for i in range(num_projects):
            ctx.obj["main"].status_console.print(
                f"Creating project {i + 1}/{num_projects}..."
            )
            project_to_create, missions_info = next(project_generator)
            created.append(
                await operations.create_project(
                    project_to_create,
                    initiator=ctx.obj["admin_user"],
                    session=session,
                    settings=settings,
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
                    initiator=ctx.obj["admin_user"],
                    session=session,
                    settings=settings,
                    event_emitter=emitter,
                )
                for record_index, record_to_create in enumerate(records_to_create):
                    # ctx.obj["main"].status_console.print(
                    #     f"\t\tCreating record ({record_index + 1}/{len(records_to_create)}) for mission..."
                    # )
                    await operations.create_survey_related_record(
                        record_to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
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
async def load_sample_projects(ctx: typer.Context):
    """Load sample projects into the database."""
    session_maker = ctx.obj["session_maker"]
    created = []
    settings = ctx.obj["main"].settings
    async with session_maker() as session:
        for to_create in sampledata.get_projects_to_create():
            try:
                created.append(
                    await operations.create_project(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Project {to_create.id!r} already exists, skipping..."
                )
                await session.rollback()
    for created_project in created:
        to_show = schemas.ProjectReadListItem(**created_project.model_dump())
        ctx.obj["main"].status_console.print(to_show)


@app.async_command()
async def load_sample_survey_missions(ctx: typer.Context):
    """Load sample survey missions into the database."""
    session_maker = ctx.obj["session_maker"]
    created = []
    settings = ctx.obj["main"].settings
    async with session_maker() as session:
        for to_create in sampledata.get_survey_missions_to_create():
            try:
                created.append(
                    await operations.create_survey_mission(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Survey mission {to_create.id!r} already exists, skipping..."
                )
                await session.rollback()
    for created_survey_mission in created:
        to_show = schemas.SurveyMissionReadListItem.from_db_instance(
            created_survey_mission
        )
        ctx.obj["main"].status_console.print(to_show)


@app.async_command()
async def load_sample_survey_related_records(ctx: typer.Context):
    """Load sample survey-related records into the database."""
    session_maker = ctx.obj["session_maker"]
    created = []
    settings = ctx.obj["main"].settings
    async with session_maker() as session:
        all_dataset_categories = await queries.collect_all_dataset_categories(session)
        all_domain_types = await queries.collect_all_domain_types(session)
        all_workflow_stages = await queries.collect_all_workflow_stages(session)
        for to_create in sampledata.get_survey_related_records_to_create(
            dataset_categories={c.name["en"]: c for c in all_dataset_categories},
            domain_types={d.name["en"]: d for d in all_domain_types},
            workflow_stages={w.name["en"]: w for w in all_workflow_stages},
        ):
            try:
                created.append(
                    await operations.create_survey_related_record(
                        to_create,
                        initiator=ctx.obj["admin_user"],
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Survey-related record {to_create.id!r} already exists, skipping..."
                )
                await session.rollback()
    for created_survey_record in created:
        to_show = schemas.SurveyRelatedRecordReadListItem.from_db_instance(
            created_survey_record
        )
        ctx.obj["main"].status_console.print(to_show)
