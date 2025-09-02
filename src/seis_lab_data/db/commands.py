import uuid

from slugify import slugify
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    errors,
    schemas,
)
from . import (
    models,
    queries,
)


async def create_dataset_category(
    session: AsyncSession,
    to_create: schemas.DatasetCategoryCreate,
) -> models.DatasetCategory:
    category = models.DatasetCategory(
        **to_create.model_dump(),
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def delete_dataset_category(
    session: AsyncSession,
    dataset_category_id: uuid.UUID,
) -> None:
    if dataset_category := (
        await queries.get_dataset_category(session, dataset_category_id)
    ):
        await session.delete(dataset_category)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Dataset category with id {dataset_category_id} does not exist."
        )


async def create_domain_type(
    session: AsyncSession,
    to_create: schemas.DomainTypeCreate,
) -> models.DomainType:
    domain_type = models.DomainType(
        **to_create.model_dump(),
    )
    session.add(domain_type)
    await session.commit()
    await session.refresh(domain_type)
    return domain_type


async def delete_domain_type(
    session: AsyncSession,
    domain_type_id: uuid.UUID,
) -> None:
    if domain_type := (await queries.get_domain_type(session, domain_type_id)):
        await session.delete(domain_type)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Domain type with id {domain_type_id} does not exist."
        )


async def create_workflow_stage(
    session: AsyncSession,
    to_create: schemas.WorkflowStageCreate,
) -> models.WorkflowStage:
    workflow_stage = models.WorkflowStage(
        **to_create.model_dump(),
    )
    session.add(workflow_stage)
    await session.commit()
    await session.refresh(workflow_stage)
    return workflow_stage


async def delete_workflow_stage(
    session: AsyncSession,
    workflow_stage_id: uuid.UUID,
) -> None:
    if workflow_stage := (await queries.get_workflow_stage(session, workflow_stage_id)):
        await session.delete(workflow_stage)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Workflow stage with id {workflow_stage_id} does not exist."
        )


async def create_project(
    session: AsyncSession, to_create: schemas.ProjectCreate
) -> models.Project:
    project = models.Project(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(
    session: AsyncSession,
    project_id: schemas.ProjectId,
) -> None:
    if project := (await queries.get_project(session, project_id)):
        await session.delete(project)
        await session.commit()
    else:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")


async def update_project(
    session: AsyncSession,
    project: models.Project,
    to_update: schemas.ProjectUpdate,
) -> models.Project:
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
        if key == "name":
            setattr(project, "slug", slugify(value.get("en", "")))
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def create_survey_mission(
    session: AsyncSession,
    to_create: schemas.SurveyMissionCreate,
) -> models.SurveyMission:
    survey_mission = models.SurveyMission(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return survey_mission


async def delete_survey_mission(
    session: AsyncSession,
    survey_mission_id: schemas.SurveyMissionId,
) -> None:
    if survey_mission := (await queries.get_survey_mission(session, survey_mission_id)):
        await session.delete(survey_mission)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id!r} does not exist."
        )


async def create_survey_related_record(
    session: AsyncSession,
    to_create: schemas.SurveyRelatedRecordCreate,
) -> models.SurveyRelatedRecord:
    survey_record = models.SurveyRelatedRecord(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(survey_record)
    await session.commit()
    await session.refresh(survey_record)
    return survey_record


async def delete_survey_related_record(
    session: AsyncSession,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
) -> None:
    if survey_record := (
        await queries.get_survey_related_record(session, survey_related_record_id)
    ):
        await session.delete(survey_record)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id!r} does not exist."
        )
