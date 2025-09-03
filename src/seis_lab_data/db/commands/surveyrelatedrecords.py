import uuid

from slugify import slugify
from sqlmodel.ext.asyncio.session import AsyncSession

from ... import (
    errors,
    schemas,
)
from .. import (
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
    return await queries.get_dataset_category(session, to_create.id)


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
    return await queries.get_domain_type(session, to_create.id)


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
    return await queries.get_workflow_stage(session, to_create.id)


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


async def create_survey_related_record(
    session: AsyncSession,
    to_create: schemas.SurveyRelatedRecordCreate,
) -> models.SurveyRelatedRecord:
    survey_record = models.SurveyRelatedRecord(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(survey_record)
    await session.commit()
    return await queries.get_survey_related_record(session, to_create.id)


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
