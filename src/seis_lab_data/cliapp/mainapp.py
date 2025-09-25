import json
import uuid
from typing import Annotated

import typer

from .. import (
    events,
    operations,
    schemas,
)
from ..db import queries
from .asynctyper import AsyncTyper

app = AsyncTyper()

dataset_categories_app = AsyncTyper()
app.add_typer(dataset_categories_app, name="dataset-categories")

domain_types_app = AsyncTyper()
app.add_typer(domain_types_app, name="domain-types")

projects_app = AsyncTyper()
app.add_typer(projects_app, name="projects")

survey_missions_app = AsyncTyper()
app.add_typer(survey_missions_app, name="survey-missions")

survey_related_records_app = AsyncTyper()
app.add_typer(survey_related_records_app, name="survey-related-records")

workflow_stages_app = AsyncTyper()
app.add_typer(workflow_stages_app, name="workflow-stages")


@app.callback()
def app_callback(ctx: typer.Context):
    """Manage system data."""


@survey_related_records_app.callback()
def survey_related_records_app_callback(ctx: typer.Context):
    """Manage survey-related records."""


@survey_related_records_app.async_command(name="create")
async def create_survey_related_record(
    ctx: typer.Context,
    parent_survey_mission_id: uuid.UUID,
    owner: str,
    name_en: str,
    name_pt: str,
    description_en: str,
    description_pt: str,
    dataset_category: str,
    domain_type: str,
    workflow_stage: str,
    relative_path: str,
    link: Annotated[list[dict], typer.Option(parser=json.loads)] = [],
):
    """Create a new survey-related record."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        if (
            db_dataset_category := await queries.get_dataset_category_by_english_name(
                session, dataset_category
            )
        ) is None:
            printer(f"dataset category '{dataset_category!r}' not found.")
            raise typer.Abort()
        if (
            db_domain_type := await queries.get_domain_type_by_english_name(
                session, domain_type
            )
        ) is None:
            printer(f"domain type '{domain_type!r}' not found.")
            raise typer.Abort()
        if (
            db_workflow_stage := await queries.get_workflow_stage_by_english_name(
                session, workflow_stage
            )
        ) is None:
            printer(f"workflow stage '{workflow_stage!r}' not found.")
            raise typer.Abort()
        if (
            survey_mission := await operations.get_survey_mission(
                schemas.SurveyMissionId(parent_survey_mission_id),
                ctx.obj["admin_user"],
                session,
                ctx.obj["main"].settings,
            )
        ) is None:
            printer(
                "Cannot create survey-related record as the parent survey "
                "mission does not exist."
            )
            raise typer.Abort()
        created = await operations.create_survey_related_record(
            to_create=schemas.SurveyRelatedRecordCreate(
                id=schemas.SurveyRelatedRecordId(uuid.uuid4()),
                owner=schemas.UserId(owner),
                name=schemas.LocalizableDraftName(en=name_en, pt=name_pt),
                description=schemas.LocalizableDraftDescription(
                    en=description_en, pt=description_pt
                ),
                survey_mission_id=schemas.SurveyMissionId(survey_mission.id),
                dataset_category_id=schemas.DatasetCategoryId(db_dataset_category.id),
                domain_type_id=schemas.DomainTypeId(db_domain_type.id),
                workflow_stage_id=schemas.WorkflowStageId(db_workflow_stage.id),
                relative_path=relative_path,
                links=[schemas.LinkSchema(**li) for li in link],
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
        ctx.obj["main"].status_console.print(
            schemas.SurveyRelatedRecordReadDetail(**created.model_dump())
        )


@survey_related_records_app.async_command(name="list")
async def list_survey_related_records(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List survey-related records."""
    async with ctx.obj["session_maker"]() as session:
        items, num_total = await operations.list_survey_related_records(
            session,
            initiator=ctx.obj["admin_user"],
            limit=limit,
            offset=offset,
            include_total=True,
        )
    ctx.obj["main"].status_console.print(f"Total records: {num_total}")
    for item in items:
        ctx.obj["main"].status_console.print_json(
            schemas.SurveyRelatedRecordReadListItem(
                **item.model_dump()
            ).model_dump_json()
        )


@survey_related_records_app.async_command(name="get")
async def get_survey_related_record(
    ctx: typer.Context, survey_related_record_id: uuid.UUID
):
    """Get details about a survey-related record."""
    async with ctx.obj["session_maker"]() as session:
        survey_record = await operations.get_survey_related_record(
            schemas.SurveyRelatedRecordId(survey_related_record_id),
            ctx.obj["admin_user"].id,
            session,
            ctx.obj["main"].settings,
        )
        if survey_record is None:
            ctx.obj["main"].status_console.print(
                f"Survey-related record {survey_related_record_id!r} not found"
            )
        else:
            ctx.obj["main"].status_console.print_json(
                schemas.SurveyRelatedRecordReadDetail.from_db_instance(
                    survey_record
                ).model_dump_json()
            )


@survey_related_records_app.async_command(name="delete")
async def delete_survey_related_record(
    ctx: typer.Context,
    survey_related_record_id: uuid.UUID,
):
    """Delete a survey-related record."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        await operations.delete_survey_related_record(
            schemas.SurveyRelatedRecordId(survey_related_record_id),
            initiator=ctx.obj["admin_user"].id,
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
    printer(f"Deleted survey-related record with id {survey_related_record_id!r}")


@survey_missions_app.callback()
def survey_missions_app_callback(ctx: typer.Context):
    """Manage survey missions."""


@survey_missions_app.async_command(name="create")
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
    async with ctx.obj["session_maker"]() as session:
        if (
            project := await operations.get_project(
                schemas.ProjectId(parent_project_id),
                ctx.obj["admin_user"],
                session,
                ctx.obj["main"].settings,
            )
        ) is None:
            ctx.obj["main"].status_console.print(
                "Cannot create survey mission as the parent project does not exist."
            )
            raise typer.Abort()
        created = await operations.create_survey_mission(
            to_create=schemas.SurveyMissionCreate(
                id=schemas.SurveyMissionId(uuid.uuid4()),
                project_id=schemas.ProjectId(project.id),
                owner=schemas.UserId(owner),
                name=schemas.LocalizableDraftName(en=name_en, pt=name_pt),
                description=schemas.LocalizableDraftDescription(
                    en=description_en, pt=description_pt
                ),
                relative_path=relative_path,
                links=[schemas.LinkSchema(**li) for li in link],
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
        ctx.obj["main"].status_console.print(
            schemas.SurveyMissionReadDetail(**created.model_dump())
        )


@survey_missions_app.async_command(name="list")
async def list_survey_missions(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List survey missions."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        items, num_total = await operations.list_survey_missions(
            session,
            initiator=ctx.obj["admin_user"],
            limit=limit,
            offset=offset,
            include_total=True,
        )
    printer(f"Total records: {num_total}")
    for item in items:
        printer(schemas.SurveyMissionReadListItem(**item.model_dump()))


@survey_missions_app.async_command(name="get")
async def get_survey_mission(ctx: typer.Context, survey_mission_id: uuid.UUID):
    """Get details about a survey mission"""
    async with ctx.obj["session_maker"]() as session:
        survey_mission = await operations.get_survey_mission(
            schemas.SurveyMissionId(survey_mission_id),
            ctx.obj["admin_user"].id,
            session,
            ctx.obj["main"].settings,
        )
        if survey_mission is None:
            ctx.obj["main"].status_console.print(
                f"Survey mission {survey_mission_id!r} not found"
            )
        else:
            ctx.obj["main"].status_console.print_json(
                schemas.SurveyMissionReadDetail.from_db_instance(
                    survey_mission
                ).model_dump_json()
            )


@survey_missions_app.async_command(name="delete")
async def delete_survey_mission(
    ctx: typer.Context,
    survey_mission_id: uuid.UUID,
):
    """Delete a survey mission."""
    printer = ctx.obj["main"].status_console.print
    async with ctx.obj["session_maker"]() as session:
        await operations.delete_survey_mission(
            schemas.SurveyMissionId(survey_mission_id),
            initiator=ctx.obj["admin_user"].id,
            session=session,
            settings=ctx.obj["main"].settings,
            event_emitter=events.get_event_emitter(ctx.obj["main"].settings),
        )
    printer(f"Deleted survey mission with id {survey_mission_id!r}")


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
    link: Annotated[list[dict], typer.Option(parser=json.loads)],
):
    """Create a new project."""
    async with ctx.obj["session_maker"]() as session:
        created = await operations.create_project(
            to_create=schemas.ProjectCreate(
                id=schemas.ProjectId(uuid.uuid4()),
                owner=schemas.UserId(owner),
                name=schemas.LocalizableDraftName(en=name_en, pt=name_pt),
                description=schemas.LocalizableDraftDescription(
                    en=description_en, pt=description_pt
                ),
                root_path=root_path,
                links=[
                    schemas.LinkSchema(
                        url=li["url"],
                        link_description=schemas.LocalizableDraftDescription(
                            en=li.get("link_description", {}).get("en", ""),
                            pt=li.get("link_description", {}).get("pt", ""),
                        ),
                        media_type=li["media_type"],
                        relation=li["relation"],
                    )
                    for li in link
                ],
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
            schemas.ProjectId(project_id),
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
                id=schemas.DatasetCategoryId(uuid.uuid4()),
                name=schemas.LocalizableDraftName(en=name_en, pt=name_pt),
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
                id=schemas.DomainTypeId(uuid.uuid4()),
                name=schemas.LocalizableDraftName(en=name_en, pt=name_pt),
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
                id=schemas.WorkflowStageId(uuid.uuid4()),
                name=schemas.LocalizableDraftName(en=name_en, pt=name_pt),
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
