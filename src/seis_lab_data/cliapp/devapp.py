import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    events,
    operations,
    schemas,
)
from ..db import queries
from . import sampledata
from .asynctyper import AsyncTyper

app = AsyncTyper()


@app.callback()
def dev_app_callback(ctx: typer.Context):
    """Dev-related commands"""


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
    for created_campaign in created:
        to_show = schemas.ProjectReadListItem(**created_campaign.model_dump())
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
        to_show = schemas.SurveyMissionReadListItem(
            **created_survey_mission.model_dump()
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
                        initiator=to_create.owner,
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
        to_show = schemas.SurveyRelatedRecordReadListItem(
            **created_survey_record.model_dump()
        )
        ctx.obj["main"].status_console.print(to_show)
