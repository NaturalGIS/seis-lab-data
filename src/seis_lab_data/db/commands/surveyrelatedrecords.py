import logging
import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import (
    errors,
    schemas,
)
from .. import (
    models,
    queries,
)

logger = logging.getLogger(__name__)


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
        **to_create.model_dump(exclude={"assets"}),
    )
    # need to ensure english name is unique for combination of mission and record
    if await queries.get_survey_related_record_by_english_name(
        session, schemas.SurveyMissionId(to_create.survey_mission_id), to_create.name.en
    ):
        raise errors.SeisLabDataError(
            f"There is already a survey-related record with english name {to_create.name.en!r} for "
            f"the same survey mission."
        )
    session.add(survey_record)
    for asset_to_create in to_create.assets:
        db_asset = models.RecordAsset(
            **asset_to_create.model_dump(),
            survey_related_record_id=survey_record.id,
        )
        session.add(db_asset)
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


async def update_survey_related_record(
    session: AsyncSession,
    survey_related_record: models.SurveyRelatedRecord,
    to_update: schemas.SurveyRelatedRecordUpdate,
):
    """Update a survey-related record and its assets.

    Updating the record also means that underlying assets may be
    added, updated, or removed.
    """
    logger.debug(f"{to_update=}")
    for key, value in to_update.model_dump(
        exclude={"assets"}, exclude_unset=True
    ).items():
        setattr(survey_related_record, key, value)
    session.add(survey_related_record)

    for proposed_asset in to_update.assets:
        try:
            existing_asset = [
                a
                for a in survey_related_record.assets
                if schemas.RecordAssetId(a.id) == proposed_asset.id
            ][0]
        except IndexError:  # this is a new asset that needs to be created
            db_asset = models.RecordAsset(
                **proposed_asset.model_dump(),
                survey_related_record_id=survey_related_record.id,
            )
            session.add(db_asset)
        else:  # this is an existing asset that needs to be updated
            for key, value in proposed_asset.model_dump(exclude_unset=True).items():
                setattr(existing_asset, key, value)
            session.add(existing_asset)

    proposed_asset_ids = [s.id for s in to_update.assets]
    for existing_asset in survey_related_record.assets:
        if schemas.RecordAssetId(existing_asset.id) not in proposed_asset_ids:
            await session.delete(existing_asset)
    await session.commit()
    return await queries.get_survey_related_record(
        session, schemas.SurveyRelatedRecordId(survey_related_record.id)
    )
