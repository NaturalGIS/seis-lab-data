import logging
import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
    events,
    permissions,
    schemas,
)
from ..db import (
    commands,
    queries,
    models,
)

logger = logging.getLogger(__name__)


async def create_dataset_category(
    to_create: schemas.DatasetCategoryCreate,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.DatasetCategory:
    if initiator is None or not permissions.can_create_dataset_category(
        initiator, to_create, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a dataset category."
        )
    dataset_category = await commands.create_dataset_category(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.DATASET_CATEGORY_CREATED,
            initiator=initiator,
            payload=schemas.EventPayload(
                after=schemas.DatasetCategoryRead(
                    **dataset_category.model_dump()
                ).model_dump()
            ),
        )
    )
    return dataset_category


async def delete_dataset_category(
    dataset_category_id: uuid.UUID,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_dataset_category(
        initiator, dataset_category_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to delete dataset categories."
        )
    dataset_category = await queries.get_dataset_category(session, dataset_category_id)
    if dataset_category is None:
        raise errors.SeisLabDataError(
            f"Dataset category with id {dataset_category_id} does not exist."
        )
    serialized_category = schemas.DatasetCategoryRead(
        **dataset_category.model_dump()
    ).model_dump()
    await commands.delete_dataset_category(session, dataset_category_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.DATASET_CATEGORY_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_category),
        )
    )


async def list_dataset_categories(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.DatasetCategory], int | None]:
    return await queries.list_dataset_categories(session, limit, offset, include_total)


async def create_domain_type(
    to_create: schemas.DomainTypeCreate,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.DomainType:
    if initiator is None or not permissions.can_create_domain_type(
        initiator, to_create, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to create a domain type.")
    domain_type = await commands.create_domain_type(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.DOMAIN_TYPE_CREATED,
            initiator=initiator,
            payload=schemas.EventPayload(
                after=schemas.DomainTypeRead(**domain_type.model_dump()).model_dump()
            ),
        )
    )
    return domain_type


async def delete_domain_type(
    domain_type_id: uuid.UUID,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_domain_type(
        initiator, domain_type_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to delete domain types.")
    domain_type = await queries.get_domain_type(session, domain_type_id)
    if domain_type is None:
        raise errors.SeisLabDataError(
            f"Domain type with id {domain_type_id} does not exist."
        )
    serialized_domain_type = schemas.DomainTypeRead(
        **domain_type.model_dump()
    ).model_dump()
    await commands.delete_domain_type(session, domain_type_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.DOMAIN_TYPE_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_domain_type),
        )
    )


async def list_domain_types(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.DomainType], int | None]:
    return await queries.list_domain_types(session, limit, offset, include_total)


async def create_workflow_stage(
    to_create: schemas.WorkflowStageCreate,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.WorkflowStage:
    if initiator is None or not permissions.can_create_workflow_stage(
        initiator, to_create, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to create a workflow stage.")
    workflow_stage = await commands.create_workflow_stage(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.WORKFLOW_STAGE_CREATED,
            initiator=initiator,
            payload=schemas.EventPayload(
                after=schemas.DomainTypeRead(**workflow_stage.model_dump()).model_dump()
            ),
        )
    )
    return workflow_stage


async def delete_workflow_stage(
    workflow_stage_id: uuid.UUID,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_workflow_stage(
        initiator, workflow_stage_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to delete workflow stages.")
    workflow_stage = await queries.get_workflow_stage(session, workflow_stage_id)
    if workflow_stage is None:
        raise errors.SeisLabDataError(
            f"Workflow stage with id {workflow_stage_id} does not exist."
        )
    serialized_workflow_stage = schemas.DomainTypeRead(
        **workflow_stage.model_dump()
    ).model_dump()
    await commands.delete_workflow_stage(session, workflow_stage_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.WORKFLOW_STAGE_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_workflow_stage),
        )
    )


async def list_workflow_stages(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.WorkflowStage], int | None]:
    return await queries.list_workflow_stages(session, limit, offset, include_total)


async def create_survey_related_record(
    to_create: schemas.SurveyRelatedRecordCreate,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
):
    if initiator is None or not await permissions.can_create_survey_related_record(
        initiator, to_create, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a survey-related record."
        )
    survey_record = await commands.create_survey_related_record(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_RELATED_RECORD_CREATED,
            initiator=initiator,
            payload=schemas.EventPayload(
                after=schemas.SurveyRelatedRecordReadDetail.from_db_instance(
                    survey_record
                ).model_dump()
            ),
        )
    )
    return survey_record


async def delete_survey_related_record(
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_survey_related_record(
        initiator, survey_related_record_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to delete survey-related record."
        )
    if (
        survey_record := await queries.get_survey_related_record(
            session, survey_related_record_id
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id!r} does not exist."
        )
    record_assets = await queries.collect_all_record_assets(
        session, survey_related_record_id
    )
    serialized_survey_record = schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        survey_record, record_assets
    ).model_dump()
    await commands.delete_survey_related_record(session, survey_related_record_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_RELATED_RECORD_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_survey_record),
        )
    )


async def list_survey_related_records(
    session: AsyncSession,
    initiator: schemas.UserId | None,
    survey_mission_filter: schemas.SurveyMissionId | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    return await queries.list_survey_related_records(
        session,
        initiator,
        survey_mission_id=survey_mission_filter,
        limit=limit,
        offset=offset,
        include_total=include_total,
    )


async def get_survey_related_record_by_slug(
    survey_related_record_slug: str,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> tuple[models.SurveyRelatedRecord, list[models.RecordAsset]] | None:
    if not permissions.can_read_survey_related_record(
        initiator, survey_related_record_slug, settings=settings
    ):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey-related "
            f"record {survey_related_record_slug!r}."
        )
    if (
        survey_related_record := await queries.get_survey_related_record_by_slug(
            session, survey_related_record_slug
        )
    ) is None:
        return None
    else:
        record_assets = await queries.collect_all_record_assets(
            session, schemas.SurveyRelatedRecordId(survey_related_record.id)
        )
        return survey_related_record, record_assets
