import asyncio
import dataclasses
import json
import uuid
from typing import Annotated

import shapely
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
    surveyrelatedrecords as record_ops,
)
from ..tasks import projects as project_tasks
from ..db import queries
from ..schemas import (
    common as common_schemas,
    identifiers,
    projects as project_schemas,
    surveymissions as mission_schemas,
    surveyrelatedrecords as record_schemas,
)
from .asynctyper import AsyncTyper
from .utils import resolve_admin_user
from . import handlers

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
def app_callback(
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
    """Manage system data."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    ctx.obj["admin_user"] = asyncio.run(
        resolve_admin_user(settings, admin_username, admin_user_id)
    )


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
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
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
            survey_mission := await mission_ops.get_survey_mission(
                identifiers.SurveyMissionId(parent_survey_mission_id),
                ctx.obj["admin_user"],
                session,
            )
        ) is None:
            printer(
                "Cannot create survey-related record as the parent survey "
                "mission does not exist."
            )
            raise typer.Abort()
        created = await record_ops.create_survey_related_record(
            to_create=record_schemas.SurveyRelatedRecordCreate(
                id=identifiers.SurveyRelatedRecordId(uuid.uuid4()),
                owner_id=identifiers.UserId(owner),
                name=common_schemas.LocalizableDraftName(en=name_en, pt=name_pt),
                description=common_schemas.LocalizableDraftDescription(
                    en=description_en, pt=description_pt
                ),
                survey_mission_id=identifiers.SurveyMissionId(survey_mission.id),
                dataset_category_id=identifiers.DatasetCategoryId(
                    db_dataset_category.id
                ),
                domain_type_id=identifiers.DomainTypeId(db_domain_type.id),
                workflow_stage_id=identifiers.WorkflowStageId(db_workflow_stage.id),
                relative_path=relative_path,
                links=[common_schemas.LinkSchema(**li) for li in link],
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        print(record_schemas.SurveyRelatedRecordReadDetail(**created.model_dump()))


@survey_related_records_app.async_command(name="list")
async def list_survey_related_records(
    ctx: typer.Context,
    page: int = 1,
    page_size: int | None = None,
):
    """List survey-related records."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    _page_size = page_size or settings.pagination_page_size
    async with settings.get_db_session_maker()() as session:
        items, num_total = await record_ops.list_survey_related_records(
            session,
            initiator=ctx.obj["admin_user"],
            page=page,
            page_size=_page_size,
            include_total=True,
        )
    ctx.obj["main"].status_console.print(f"Total records: {num_total}")
    for item in items:
        # ctx.obj["main"].status_console.print_json(item.model_dump_json())
        print(
            record_schemas.SurveyRelatedRecordReadListItem.from_db_instance(
                item
            ).model_dump_json()
        )


@survey_related_records_app.async_command(name="get")
async def get_survey_related_record(
    ctx: typer.Context, survey_related_record_id: uuid.UUID
):
    """Get details about a survey-related record."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        record_details = await record_ops.get_survey_related_record(
            identifiers.SurveyRelatedRecordId(survey_related_record_id),
            ctx.obj["admin_user"].id,
            session,
        )
        if record_details is None:
            ctx.obj["main"].status_console.print(
                f"Survey-related record {survey_related_record_id!r} not found"
            )
        else:
            print(
                record_schemas.SurveyRelatedRecordReadDetail.from_db_instance(
                    *record_details
                ).model_dump_json()
            )


@survey_related_records_app.async_command(name="delete")
async def delete_survey_related_record(
    ctx: typer.Context,
    survey_related_record_id: uuid.UUID,
):
    """Delete a survey-related record."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    printer = ctx.obj["main"].status_console.print
    async with settings.get_db_session_maker()() as session:
        await record_ops.delete_survey_related_record(
            identifiers.SurveyRelatedRecordId(survey_related_record_id),
            initiator=ctx.obj["admin_user"].id,
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
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


@survey_missions_app.async_command(name="list")
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


@survey_missions_app.async_command(name="get")
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


@survey_missions_app.async_command(name="delete")
async def delete_survey_mission(
    ctx: typer.Context,
    survey_mission_id: uuid.UUID,
):
    """Delete a survey mission."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await mission_ops.delete_survey_mission(
            identifiers.SurveyMissionId(survey_mission_id),
            initiator=ctx.obj["admin_user"].id,
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted survey mission with id {survey_mission_id!r}")


@projects_app.callback()
def projects_app_callback(ctx: typer.Context):
    """Manage projects."""


def _parse_bbox_bounds(raw_bounds: str) -> shapely.Polygon:
    bounds = [float(coord) for coord in raw_bounds.split(",")]
    if len(bounds) != 4:
        raise ValueError("Bounds must have exactly four comma-separated values.")
    min_lon, min_lat, max_lon, max_lat = bounds
    return shapely.box(min_lon, min_lat, max_lon, max_lat)


@projects_app.async_command(name="create")
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


@projects_app.async_command(name="get")
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


@projects_app.async_command(name="list")
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


@projects_app.async_command(name="delete")
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


@projects_app.async_command(name="old-delete")
async def old_delete_project(
    ctx: typer.Context,
    project_id: uuid.UUID,
):
    """Delete a project."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await project_ops.delete_project(
            identifiers.ProjectId(project_id),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted project with id {project_id!r}")


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
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        created = await record_ops.create_dataset_category(
            to_create=record_schemas.DatasetCategoryCreate(
                id=identifiers.DatasetCategoryId(uuid.uuid4()),
                name=common_schemas.LocalizableDraftName(en=name_en, pt=name_pt),
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        print(record_schemas.DatasetCategoryRead(**created.model_dump()))


@dataset_categories_app.async_command(name="list")
async def list_dataset_categories(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List dataset categories."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        items, num_total = await record_ops.list_dataset_categories(
            session, limit=limit, offset=offset, include_total=True
        )
    print(f"Total records: {num_total}")
    for item in items:
        print(record_schemas.DatasetCategoryRead(**item.model_dump()))


@dataset_categories_app.async_command(name="delete")
async def delete_dataset_category(
    ctx: typer.Context,
    dataset_category_id: uuid.UUID,
):
    """Delete a dataset category."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await record_ops.delete_dataset_category(
            dataset_category_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted dataset category with id {dataset_category_id!r}")


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
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        created = await record_ops.create_domain_type(
            to_create=record_schemas.DomainTypeCreate(
                id=identifiers.DomainTypeId(uuid.uuid4()),
                name=common_schemas.LocalizableDraftName(en=name_en, pt=name_pt),
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        print(record_schemas.DomainTypeRead(**created.model_dump()))


@domain_types_app.async_command(name="list")
async def list_domain_types(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List domain types."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        items, num_total = await record_ops.list_domain_types(
            session, limit=limit, offset=offset, include_total=True
        )
    print(f"Total records: {num_total}")
    for item in items:
        print(record_schemas.DomainTypeRead(**item.model_dump()))


@domain_types_app.async_command(name="delete")
async def delete_domain_type(
    ctx: typer.Context,
    domain_type_id: uuid.UUID,
):
    """Delete a domain type."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await record_ops.delete_domain_type(
            domain_type_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted domain type with id {domain_type_id!r}")


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
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        created = await record_ops.create_workflow_stage(
            to_create=record_schemas.WorkflowStageCreate(
                id=identifiers.WorkflowStageId(uuid.uuid4()),
                name=common_schemas.LocalizableDraftName(en=name_en, pt=name_pt),
            ),
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        print(record_schemas.WorkflowStageRead(**created.model_dump()))


@workflow_stages_app.async_command(name="list")
async def list_workflow_stages(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List workflow stages."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        items, num_total = await record_ops.list_workflow_stages(
            session, limit=limit, offset=offset, include_total=True
        )
    print(f"Total records: {num_total}")
    for item in items:
        print(record_schemas.WorkflowStageRead(**item.model_dump()))


@workflow_stages_app.async_command(name="delete")
async def delete_workflow_stage(
    ctx: typer.Context,
    workflow_stage_id: uuid.UUID,
):
    """Delete a workflow stage."""
    settings: config.SeisLabDataSettings = ctx.obj["main"].settings
    async with settings.get_db_session_maker()() as session:
        await record_ops.delete_workflow_stage(
            workflow_stage_id,
            initiator=ctx.obj["admin_user"],
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
    print(f"Deleted workflow stage with id {workflow_stage_id!r}")
