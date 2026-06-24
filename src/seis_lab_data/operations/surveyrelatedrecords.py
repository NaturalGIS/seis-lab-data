import asyncio
import logging
import uuid

import pydantic
import shapely
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    dispatch,
    errors,
)
from ..permissions import surveyrelatedrecords as record_permissions
from ..constants import (
    ROLE_ADMIN,
    ROLE_SYSTEM_ADMIN,
    ProjectStatus,
    SurveyMissionStatus,
    SurveyRelatedRecordStatus,
)
from ..db import models
from ..db.commands import surveyrelatedrecords as record_commands
from ..db.queries import (
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
)
from ..schemas import (
    events as event_schemas,
    filters as filter_schemas,
    identifiers,
    surveyrelatedrecords as record_schemas,
    user as user_schemas,
    validation as validation_schemas,
)
from . import surveymissions as survey_mission_ops

logger = logging.getLogger(__name__)


async def create_dataset_category(
    *,
    request_id: identifiers.RequestId,
    to_create: record_schemas.DatasetCategoryCreate,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.DatasetCategory:
    if not record_permissions.can_create_dataset_category(initiator):
        raise errors.SeisLabDataError(
            "User is not allowed to create a dataset category."
        )
    dataset_category = await record_commands.create_dataset_category(session, to_create)
    await event_dispatcher(
        event_schemas.DatasetCategoryCreatedEvent(
            category_id=identifiers.DatasetCategoryId(dataset_category.id),
            initiator=initiator.id,
        )
    )
    return dataset_category


async def delete_dataset_category(
    *,
    request_id: identifiers.RequestId,
    dataset_category_id: uuid.UUID,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    if not record_permissions.can_delete_dataset_category(initiator):
        raise errors.SeisLabDataError(
            "User is not allowed to delete dataset categories."
        )
    dataset_category = await record_queries.get_dataset_category(
        session, dataset_category_id
    )
    if dataset_category is None:
        raise errors.SeisLabDataError(
            f"Dataset category with id {dataset_category_id} does not exist."
        )
    await record_commands.delete_dataset_category(session, dataset_category_id)
    await event_dispatcher(
        event_schemas.DatasetCategoryDeletedEvent(
            category_id=identifiers.DatasetCategoryId(dataset_category.id),
            initiator=initiator.id,
        )
    )


async def list_dataset_categories(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.DatasetCategory], int | None]:
    return await record_queries.list_dataset_categories(
        session, limit, offset, include_total
    )


async def create_workflow_stage(
    *,
    request_id: identifiers.RequestId,
    to_create: record_schemas.WorkflowStageCreate,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.WorkflowStage:
    if not record_permissions.can_create_workflow_stage(initiator):
        raise errors.SeisLabDataError("User is not allowed to create a workflow stage.")
    workflow_stage = await record_commands.create_workflow_stage(session, to_create)
    await event_dispatcher(
        event_schemas.WorkflowStageCreatedEvent(
            stage_id=identifiers.WorkflowStageId(workflow_stage.id),
            initiator=initiator.id,
        )
    )
    return workflow_stage


async def delete_workflow_stage(
    workflow_stage_id: uuid.UUID,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    if not record_permissions.can_delete_workflow_stage(initiator):
        raise errors.SeisLabDataError("User is not allowed to delete workflow stages.")
    workflow_stage = await record_queries.get_workflow_stage(session, workflow_stage_id)
    if workflow_stage is None:
        raise errors.SeisLabDataError(
            f"Workflow stage with id {workflow_stage_id} does not exist."
        )
    await record_commands.delete_workflow_stage(session, workflow_stage_id)
    await event_dispatcher(
        event_schemas.WorkflowStageDeletedEvent(
            stage_id=identifiers.WorkflowStageId(workflow_stage.id),
            initiator=initiator.id,
        )
    )


async def list_workflow_stages(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.WorkflowStage], int | None]:
    return await record_queries.list_workflow_stages(
        session, limit, offset, include_total
    )


async def create_survey_related_record(
    *,
    request_id: identifiers.RequestId,
    to_create: record_schemas.SurveyRelatedRecordCreate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
):
    try:
        if not (
            survey_mission := await mission_queries.get_survey_mission(
                session, to_create.survey_mission_id
            )
        ):
            raise errors.SeisLabDataError(
                f"Survey mission with id {to_create.survey_mission_id} does not exist"
            )
        if not record_permissions.can_create_survey_related_record(
            initiator, survey_mission
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to create a survey-related record."
            )
        if (mission_status := survey_mission.status) not in (
            SurveyMissionStatus.DRAFT,
            SurveyMissionStatus.UNDER_DISCOVERY,
        ):
            raise errors.SeisLabDataError(
                f"Cannot create survey-related record because parent survey "
                f"mission's status is {mission_status}"
            )
        if (project_status := survey_mission.project.status) not in (
            ProjectStatus.DRAFT,
            ProjectStatus.UNDER_DISCOVERY,
        ):
            raise errors.SeisLabDataError(
                f"Cannot create survey-related record because parent project's "
                f"status is {project_status}"
            )
        survey_record = await record_commands.create_survey_related_record(
            session, to_create
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.SurveyRelatedRecordNotCreatedEvent(
                initiator=initiator.id, request_id=request_id, details=str(err)
            )
        )
        return None

    await event_dispatcher(
        event_schemas.SurveyRelatedRecordCreatedEvent(
            request_id=request_id,
            record_id=identifiers.SurveyRelatedRecordId(survey_record.id),
            survey_mission_id=identifiers.SurveyMissionId(
                survey_record.survey_mission_id
            ),
            project_id=identifiers.ProjectId(survey_record.survey_mission.project_id),
            initiator=initiator.id,
        )
    )
    return survey_record


async def change_survey_related_record_status(
    *,
    request_id: identifiers.RequestId,
    target_status: SurveyRelatedRecordStatus,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyRelatedRecord | None:
    try:
        if (
            survey_related_record := await record_queries.get_survey_related_record(
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
        if not record_permissions.can_change_survey_related_record_status(
            initiator, survey_related_record
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to change survey-related record's status."
            )
        if target_status == SurveyRelatedRecordStatus.UNDER_DISCOVERY:
            await survey_mission_ops.change_survey_mission_status(
                request_id=request_id,
                target_status=SurveyMissionStatus.UNDER_DISCOVERY,
                survey_mission_id=identifiers.SurveyMissionId(
                    survey_related_record.survey_mission_id
                ),
                initiator=initiator,
                session=session,
                event_dispatcher=event_dispatcher,
            )
        updated_survey_related_record = (
            await record_commands.set_survey_related_record_status(
                session,
                identifiers.SurveyRelatedRecordId(survey_related_record.id),
                target_status,
            )
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.SurveyRelatedRecordStatusNotChangedEvent(
                record_id=survey_related_record_id,
                request_id=request_id,
                initiator=initiator.id,
                details=str(err),
            )
        )
        return None
    await event_dispatcher(
        event_schemas.SurveyRelatedRecordStatusChangedEvent(
            request_id=request_id,
            record_id=survey_related_record_id,
            old_status=old_status,
            new_status=updated_survey_related_record.status,
            initiator=initiator.id,
        )
    )
    return updated_survey_related_record


async def validate_survey_related_record(
    request_id: identifiers.RequestId,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyRelatedRecord | None:
    try:
        if (
            survey_related_record := await record_queries.get_survey_related_record(
                session, survey_related_record_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                f"Survey-related record with id {survey_related_record_id} does not exist."
            )
        if not record_permissions.can_validate_survey_related_record(
            initiator, survey_related_record
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to validate survey-related record."
            )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.SurveyRelatedRecordNotValidatedEvent(
                request_id=request_id,
                initiator=initiator.id,
                record_id=survey_related_record_id,
                details=str(err),
            )
        )
        return None

    validation_errors = []
    try:
        await change_survey_related_record_status(
            request_id=request_id,
            target_status=SurveyRelatedRecordStatus.UNDER_VALIDATION,
            survey_related_record_id=survey_related_record_id,
            initiator=initiator,
            session=session,
            event_dispatcher=event_dispatcher,
        )
        await asyncio.sleep(3)
        validation_schemas.ValidSurveyRelatedRecord.model_validate(
            survey_related_record
        )
    except pydantic.ValidationError as err:
        for error in err.errors():
            validation_errors.append(
                {
                    "name": ".".join(str(i) for i in error["loc"]),
                    "message": error["msg"],
                    "type_": error["type"],
                }
            )
        await record_commands.update_survey_related_record_validation_result(
            session,
            survey_related_record,
            validation_result={
                "is_valid": False,
                "errors": validation_errors,
            },
        )
    else:
        await record_commands.update_survey_related_record_validation_result(
            session,
            survey_related_record,
            validation_result={"is_valid": True, "errors": None},
        )
    finally:
        await event_dispatcher(
            event_schemas.SurveyRelatedRecordValidatedEvent(
                request_id=request_id,
                record_id=survey_related_record_id,
                is_valid=not validation_errors,
                initiator=initiator.id,
            )
        )
    await change_survey_related_record_status(
        request_id=request_id,
        target_status=SurveyRelatedRecordStatus.DRAFT,
        survey_related_record_id=survey_related_record_id,
        initiator=initiator,
        session=session,
        event_dispatcher=event_dispatcher,
    )
    return survey_related_record


async def delete_survey_related_record(
    *,
    request_id: identifiers.RequestId,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    try:
        if (
            survey_record := await record_queries.get_survey_related_record(
                session, survey_related_record_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                f"Survey-related record with id {survey_related_record_id!r} does not exist."
            )
        survey_mission_id = identifiers.SurveyMissionId(survey_record.survey_mission_id)
        project_id = identifiers.ProjectId(survey_record.survey_mission.project_id)
        if not record_permissions.can_delete_survey_related_record(
            initiator, survey_record
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to delete survey-related record."
            )
        if (
            mission_status := survey_record.survey_mission.status
        ) != SurveyMissionStatus.DRAFT:
            raise errors.SeisLabDataError(
                f"Cannot update survey-related record because parent survey "
                f"mission's status is {mission_status}"
            )
        if (
            project_status := survey_record.survey_mission.project.status
        ) != ProjectStatus.DRAFT:
            raise errors.SeisLabDataError(
                f"Cannot update survey-related record because parent project's "
                f"status is {project_status}"
            )
        await record_commands.delete_survey_related_record(
            session, survey_related_record_id
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.SurveyRelatedRecordNotDeletedEvent(
                request_id=request_id,
                record_id=survey_related_record_id,
                initiator=initiator.id,
                details=str(err),
            )
        )
        return None
    await event_dispatcher(
        event_schemas.SurveyRelatedRecordDeletedEvent(
            request_id=request_id,
            record_id=survey_related_record_id,
            survey_mission_id=survey_mission_id,
            project_id=project_id,
            initiator=initiator.id,
        )
    )


async def list_survey_related_records(
    session: AsyncSession,
    initiator: user_schemas.User | None,
    survey_mission_id: identifiers.SurveyMissionId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: filter_schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    kwargs = dict(
        survey_mission_id=survey_mission_id,
        page=page,
        page_size=page_size,
        include_total=include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
        temporal_extent=temporal_extent,
    )
    if initiator is None:
        return await record_queries.list_published_survey_related_records(
            session, **kwargs
        )
    elif not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(initiator.roles):
        return await record_queries.list_survey_related_records(session, **kwargs)
    else:
        return await record_queries.list_accessible_survey_related_records(
            session, initiator.id, **kwargs
        )


async def get_survey_related_record(
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    initiator: user_schemas.User | None,
    session: AsyncSession,
) -> (
    tuple[
        models.SurveyRelatedRecord,
        list[tuple[str, models.SurveyRelatedRecord]],
        list[tuple[str, models.SurveyRelatedRecord]],
    ]
    | None
):
    record = await record_queries.get_survey_related_record(
        session, survey_related_record_id
    )
    if record is None:
        return None
    if not record_permissions.can_read_survey_related_record(initiator, record):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey-related "
            f"record {survey_related_record_id!r}."
        )
    record_id: identifiers.SurveyRelatedRecordId = record.id
    records_related_to = (
        await record_queries.list_survey_related_record_related_to_records(
            session, record_id
        )
    )
    records_subject_for = (
        await record_queries.list_survey_related_record_subject_records(
            session, record_id
        )
    )
    return record, records_related_to, records_subject_for


async def update_survey_related_record(
    request_id: identifiers.RequestId,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    to_update: record_schemas.SurveyRelatedRecordUpdate,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyRelatedRecord:
    if (
        survey_related_record := await record_queries.get_survey_related_record(
            session, survey_related_record_id
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id} does not exist."
        )
    if not record_permissions.can_update_survey_related_record(
        initiator, survey_related_record
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to update survey-related record."
        )
    if (
        mission_status := survey_related_record.survey_mission.status
    ) != SurveyMissionStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot update survey-related record because parent survey "
            f"mission's status is {mission_status}"
        )
    if (
        project_status := survey_related_record.survey_mission.project.status
    ) != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot update survey-related record because parent project's "
            f"status is {project_status}"
        )
    updated_survey_related_record = await record_commands.update_survey_related_record(
        session, survey_related_record, to_update
    )
    await event_dispatcher(
        event_schemas.SurveyRelatedRecordUpdatedEvent(
            record_id=survey_related_record_id,
            initiator=initiator.id,
        )
    )
    return updated_survey_related_record
