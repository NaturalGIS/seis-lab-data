import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    events,
    operations,
    schemas,
)
from . import sampledata
from .asynctyper import AsyncTyper

app = AsyncTyper()


@app.callback()
def dev_app_callback(ctx: typer.Context):
    """Dev-related commands"""


@app.async_command()
async def load_sample_projects(ctx: typer.Context):
    """Load sample projects into the database."""
    session_maker = ctx.obj["session_maker"]
    created = []
    settings = ctx.obj["main"].settings
    async with session_maker() as session:
        for to_create in sampledata.PROJECTS_TO_CREATE:
            try:
                created.append(
                    await operations.create_project(
                        to_create,
                        initiator=to_create.owner,
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
        for to_create in sampledata.SURVEY_MISSIONS_TO_CREATE:
            try:
                created.append(
                    await operations.create_survey_mission(
                        to_create,
                        initiator=to_create.owner,
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
