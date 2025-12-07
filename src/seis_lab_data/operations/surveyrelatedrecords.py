import logging
import uuid

import pydantic
import shapely
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
    events,
    permissions,
    schemas,
)
from ..constants import SurveyRelatedRecordStatus
from ..db import (
    commands,
    queries,
    models,
)

logger = logging.getLogger(__name__)


async def create_dataset_category(
    to_create: schemas.DatasetCategoryCreate,
    initiator: schemas.User | None,
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
            initiator=initiator.id,
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
    initiator: schemas.User | None,
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
            initiator=initiator.id,
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
    initiator: schemas.User | None,
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
            initiator=initiator.id,
            payload=schemas.EventPayload(
                after=schemas.DomainTypeRead(**domain_type.model_dump()).model_dump()
            ),
        )
    )
    return domain_type


async def delete_domain_type(
    domain_type_id: uuid.UUID,
    initiator: schemas.User | None,
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
            initiator=initiator.id,
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
    initiator: schemas.User | None,
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
            initiator=initiator.id,
            payload=schemas.EventPayload(
                after=schemas.DomainTypeRead(**workflow_stage.model_dump()).model_dump()
            ),
        )
    )
    return workflow_stage


async def delete_workflow_stage(
    workflow_stage_id: uuid.UUID,
    initiator: schemas.User | None,
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
            initiator=initiator.id,
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
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
):
    if initiator is None or not await permissions.can_create_survey_related_record(
        initiator,
        schemas.SurveyMissionId(to_create.survey_mission_id),
        settings=settings,
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a survey-related record."
        )
    survey_record = await commands.create_survey_related_record(session, to_create)
    related_to = await queries.list_survey_related_record_related_to_records(
        session, schemas.SurveyRelatedRecordId(survey_record.id)
    )
    subject_for = await queries.list_survey_related_record_subject_records(
        session, schemas.SurveyRelatedRecordId(survey_record.id)
    )
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_RELATED_RECORD_CREATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                after=schemas.SurveyRelatedRecordReadDetail.from_db_instance(
                    survey_record,
                    records_related_to=related_to,
                    records_subject_for=subject_for,
                ).model_dump()
            ),
        )
    )
    return survey_record


async def change_survey_related_record_status(
    target_status: SurveyRelatedRecordStatus,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.SurveyRelatedRecord:
    if (
        initiator is None
        or not await permissions.can_change_survey_related_record_status(
            initiator, survey_related_record_id, settings=settings
        )
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to change survey-related record's status."
        )
    if (
        survey_related_record := await queries.get_survey_related_record(
            session, survey_related_record_id
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id} does not exist."
        )
    if (old_status := survey_related_record.status) == target_status:
        logger.info(
            f"Survey-related record status is already "
            f"set to {target_status} - nothing to do"
        )
        return survey_related_record
    else:
        updated_survey_related_record = await commands.set_survey_related_record_status(
            session,
            schemas.SurveyRelatedRecordId(survey_related_record.id),
            target_status,
        )
        event_emitter(
            schemas.SeisLabDataEvent(
                type_=schemas.EventType.SURVEY_RELATED_RECORD_STATUS_CHANGED,
                initiator=initiator.id,
                payload=schemas.EventPayload(
                    before={"status": old_status.value},
                    after={"status": updated_survey_related_record.status.value},
                ),
            )
        )
        return updated_survey_related_record


async def validate_survey_related_record(
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.SurveyRelatedRecord:
    if initiator is None or not await permissions.can_validate_survey_related_record(
        initiator, survey_related_record_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to validate survey-related record."
        )
    if (
        survey_related_record := await queries.get_survey_related_record(
            session, survey_related_record_id
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id} does not exist."
        )

    old_validation_result = survey_related_record.validation_result or {
        "is_valid": False,
        "errors": None,
    }
    validation_errors = []
    try:
        schemas.ValidSurveyRelatedRecord(**survey_related_record.model_dump())
    except pydantic.ValidationError as err:
        for error in err.errors():
            validation_errors.append(
                {
                    "name": ".".join(str(i) for i in error["loc"]),
                    "message": error["msg"],
                    "type_": error["type"],
                }
            )
        await commands.update_survey_related_record_validation_result(
            session,
            survey_related_record,
            validation_result={
                "is_valid": False,
                "errors": validation_errors,
            },
        )
    else:
        await commands.update_survey_related_record_validation_result(
            session,
            survey_related_record,
            validation_result={"is_valid": True, "errors": None},
        )
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_RELATED_RECORD_VALIDATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                before={
                    "survey_related_record_id": survey_related_record.id,
                    "validation_result": {**old_validation_result},
                },
                after={
                    "survey_related_record_id": survey_related_record.id,
                    "validation_result": {**survey_related_record.validation_result},
                },
            ),
        )
    )
    return survey_related_record


async def delete_survey_related_record(
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    initiator: schemas.User | None,
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
    serialized_survey_record = schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        survey_record
    ).model_dump()
    await commands.delete_survey_related_record(session, survey_related_record_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_RELATED_RECORD_DELETED,
            initiator=initiator.id,
            payload=schemas.EventPayload(before=serialized_survey_record),
        )
    )


async def list_survey_related_records(
    session: AsyncSession,
    initiator: schemas.UserId | None,
    survey_mission_id: schemas.SurveyMissionId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    return await queries.paginated_list_survey_related_records(
        session,
        initiator,
        survey_mission_id=survey_mission_id,
        page=page,
        page_size=page_size,
        include_total=include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
        temporal_extent=temporal_extent,
    )


async def get_survey_related_record(
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> (
    tuple[
        models.SurveyRelatedRecord,
        list[tuple[str, models.SurveyRelatedRecord]],
        list[tuple[str, models.SurveyRelatedRecord]],
    ]
    | None
):
    if not await permissions.can_read_survey_related_record(
        initiator, survey_related_record_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey-related "
            f"record {survey_related_record_id!r}."
        )
    record = await queries.get_survey_related_record(session, survey_related_record_id)
    if record:
        record_id: schemas.SurveyRelatedRecordId = record.id
        records_related_to = (
            await queries.list_survey_related_record_related_to_records(
                session, record_id
            )
        )
        records_subject_for = await queries.list_survey_related_record_subject_records(
            session, record_id
        )
        return record, records_related_to, records_subject_for
    else:
        return None


async def update_survey_related_record(
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    to_update: schemas.SurveyRelatedRecordUpdate,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.SurveyRelatedRecord:
    if initiator is None or not await permissions.can_update_survey_related_record(
        initiator, survey_related_record_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to update survey-related record."
        )
    if (
        survey_related_record := await queries.get_survey_related_record(
            session, survey_related_record_id
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id} does not exist."
        )
    serialized_before = schemas.SurveyRelatedRecordReadDetail.from_db_instance(
        survey_related_record
    ).model_dump()
    updated_survey_related_record = await commands.update_survey_related_record(
        session, survey_related_record, to_update
    )
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_UPDATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                before=serialized_before,
                after=schemas.SurveyRelatedRecordReadDetail.from_db_instance(
                    updated_survey_related_record
                ).model_dump(),
            ),
        )
    )
    return updated_survey_related_record
