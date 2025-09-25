import random
import uuid
from itertools import count

from typing import (
    Generator,
    Sequence,
)

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


def generate_sample_projects(
    owners: Sequence[schemas.UserId],
    dataset_categories: Sequence[schemas.DatasetCategoryId],
    domain_types: Sequence[schemas.DomainTypeId],
    workflow_stages: Sequence[schemas.WorkflowStageId],
) -> Generator[
    tuple[
        schemas.ProjectCreate,
        list[
            tuple[schemas.SurveyMissionCreate, list[schemas.SurveyRelatedRecordCreate]]
        ],
    ],
    None,
    None,
]:
    for index in count():
        project = schemas.ProjectCreate(
            id=schemas.ProjectId(uuid.uuid4()),
            owner=random.choice(owners),
            name=schemas.LocalizableDraftName(
                en=f"Sample Project {index}", pt=f"Projeto de amostra {index}"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is a sample project created for testing purposes.",
                pt="Este é um projeto de amostra criado para fins de teste.",
            ),
            root_path="/project-path-{index}",
            links=[],
        )
        mission_generator = generate_sample_survey_missions(
            owners, project.id, dataset_categories, domain_types, workflow_stages
        )
        missions = [next(mission_generator) for _ in range(random.randint(1, 10))]
        yield project, missions


def generate_sample_survey_missions(
    owners: Sequence[schemas.UserId],
    project_id: schemas.ProjectId,
    dataset_categories: Sequence[schemas.DatasetCategoryId],
    domain_types: Sequence[schemas.DomainTypeId],
    workflow_stages: Sequence[schemas.WorkflowStageId],
) -> Generator[
    tuple[schemas.SurveyMissionCreate, list[schemas.SurveyRelatedRecordCreate]],
    None,
    None,
]:
    for index in count():
        mission = schemas.SurveyMissionCreate(
            id=schemas.SurveyMissionId(uuid.uuid4()),
            project_id=project_id,
            owner=random.choice(owners),
            name=schemas.LocalizableDraftName(
                en=f"Sample Survey Mission {index}", pt=f"Missão de amostra {index}"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is a sample survey mission created for testing purposes.",
                pt="Esta é uma missão de amostra criada para fins de teste.",
            ),
            relative_path="mission-path-{index}",
            links=[],
        )
        record_generator = generate_sample_survey_related_records(
            owners, mission.id, dataset_categories, domain_types, workflow_stages
        )
        records = [next(record_generator) for _ in range(random.randint(1, 100))]
        yield mission, records


def generate_sample_survey_related_records(
    owners: Sequence[schemas.UserId],
    survey_mission_id: schemas.SurveyMissionId,
    dataset_categories: Sequence[schemas.DatasetCategoryId],
    domain_types: Sequence[schemas.DomainTypeId],
    workflow_stages: Sequence[schemas.WorkflowStageId],
) -> Generator[schemas.SurveyRelatedRecordCreate, None, None]:
    for index in count():
        asset_generator = generate_sample_assets()
        yield schemas.SurveyRelatedRecordCreate(
            id=schemas.SurveyRelatedRecordId(uuid.uuid4()),
            owner=random.choice(owners),
            name=schemas.LocalizableDraftName(
                en=f"Sample Survey Related Record {index}",
                pt=f"Registo de amostra {index}",
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is a sample survey-related record created for testing purposes.",
                pt="Este é um registo de amostra criado para fins de teste.",
            ),
            survey_mission_id=survey_mission_id,
            dataset_category_id=random.choice(dataset_categories),
            domain_type_id=random.choice(domain_types),
            workflow_stage_id=random.choice(workflow_stages),
            relative_path="some-path-{index}",
            links=[],
            assets=[next(asset_generator) for _ in range(random.randint(1, 12))],
        )


def generate_sample_assets() -> Generator[schemas.RecordAssetCreate, None, None]:
    for index in count():
        yield schemas.RecordAssetCreate(
            id=schemas.RecordAssetId(uuid.uuid4()),
            name=schemas.LocalizableDraftName(
                en=f"Sample Asset {index}", pt=f"Recurso de amostra {index}"
            ),
            description=schemas.LocalizableDraftDescription(
                en="This is a sample asset created for testing purposes.",
                pt="Este é um recurso de amostra criado para fins de teste.",
            ),
            relative_path=f"some-path-{index}",
            links=[],
        )
