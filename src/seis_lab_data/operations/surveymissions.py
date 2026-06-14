import logging

import pydantic
import shapely
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    dispatch,
    errors,
)
from ..constants import (
    ROLE_ADMIN,
    ROLE_SYSTEM_ADMIN,
    ProjectStatus,
    SurveyMissionStatus,
)
from ..db import (
    commands,
    queries,
    models,
)
from .. import permissions
from ..schemas import (
    events as event_schemas,
    filters as filter_schemas,
    identifiers,
    surveymissions as survey_mission_schemas,
    user as user_schemas,
    validation as validation_schemas,
)
from . import projects as project_ops

logger = logging.getLogger(__name__)


async def create_survey_mission(
    to_create: survey_mission_schemas.SurveyMissionCreate,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyMission:
    if not (project := await queries.get_project(session, to_create.project_id)):
        raise errors.SeisLabDataError(
            f"Project with id {to_create.project_id} does not exist"
        )
    if not permissions.can_create_survey_mission(initiator, project):
        raise errors.SeisLabDataError(
            f"User {initiator!r} is not allowed to create a survey mission."
        )
    if (project_status := project.status) not in (
        ProjectStatus.DRAFT,
        ProjectStatus.UNDER_DISCOVERY,
    ):
        raise errors.SeisLabDataError(
            f"Cannot create survey mission because parent project's "
            f"status is {project_status}"
        )
    survey_mission = await commands.create_survey_mission(session, to_create)
    await event_dispatcher(
        event_schemas.SurveyMissionCreatedEvent(
            survey_mission_id=identifiers.SurveyMissionId(survey_mission.id),
            project_id=identifiers.ProjectId(survey_mission.project_id),
            initiator=initiator.id,
        )
    )
    return survey_mission


async def change_survey_mission_status(
    target_status: SurveyMissionStatus,
    survey_mission_id: identifiers.SurveyMissionId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyMission:
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id} does not exist."
        )
    if not permissions.can_change_survey_mission_status(initiator, survey_mission):
        raise errors.SeisLabDataError(
            "User is not allowed to change survey mission status."
        )
    if (old_status := survey_mission.status) == target_status:
        logger.info(
            f"Survey mission status is already set to {target_status} - nothing to do"
        )
        return survey_mission
    if target_status == SurveyMissionStatus.UNDER_DISCOVERY:
        await project_ops.change_project_status(
            ProjectStatus.UNDER_DISCOVERY,
            identifiers.ProjectId(survey_mission.project_id),
            initiator,
            session,
            event_dispatcher,
        )
    updated_survey_mission = await commands.set_survey_mission_status(
        session, identifiers.SurveyMissionId(survey_mission.id), target_status
    )
    await event_dispatcher(
        event_schemas.SurveyMissionStatusChangedEvent(
            survey_mission_id=survey_mission_id,
            old_status=old_status,
            new_status=updated_survey_mission.status,
            initiator=initiator.id,
        )
    )
    return updated_survey_mission


async def validate_survey_mission(
    survey_mission_id: identifiers.SurveyMissionId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyMission:
    await change_survey_mission_status(
        SurveyMissionStatus.UNDER_VALIDATION,
        survey_mission_id,
        initiator,
        session,
        event_dispatcher,
    )
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id} does not exist."
        )
    if not permissions.can_validate_survey_mission(initiator, survey_mission):
        raise errors.SeisLabDataError("User is not allowed to validate survey mission.")
    validation_errors = []
    try:
        validation_schemas.ValidSurveyMission(**survey_mission.model_dump())
    except pydantic.ValidationError as err:
        for error in err.errors():
            validation_errors.append(
                {
                    "name": ".".join(str(i) for i in error["loc"]),
                    "message": error["msg"],
                    "type_": error["type"],
                }
            )
        await commands.update_survey_mission_validation_result(
            session,
            survey_mission,
            validation_result={
                "is_valid": False,
                "errors": validation_errors,
            },
        )
    else:
        await commands.update_survey_mission_validation_result(
            session,
            survey_mission,
            validation_result={"is_valid": True, "errors": None},
        )
    await event_dispatcher(
        event_schemas.SurveyMissionValidatedEvent(
            survey_mission_id=survey_mission_id,
            is_valid=not validation_errors,
            initiator=initiator.id,
        )
    )
    await change_survey_mission_status(
        SurveyMissionStatus.DRAFT,
        survey_mission_id,
        initiator,
        session,
        event_dispatcher,
    )
    return survey_mission


async def update_survey_mission(
    survey_mission_id: identifiers.SurveyMissionId,
    to_update: survey_mission_schemas.SurveyMissionUpdate,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.SurveyMission:
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id} does not exist."
        )
    if not permissions.can_update_survey_mission(initiator, survey_mission):
        raise errors.SeisLabDataError("User is not allowed to update survey mission.")
    if survey_mission.status != SurveyMissionStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission with status {survey_mission.status}"
        )
    if survey_mission.project.status != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission because parent project's status "
            f"is {survey_mission.project.status}"
        )
    updated_survey_mission = await commands.update_survey_mission(
        session, survey_mission, to_update
    )
    await event_dispatcher(
        event_schemas.SurveyMissionUpdatedEvent(
            survey_mission_id=survey_mission_id,
            initiator=initiator.id,
        )
    )
    return updated_survey_mission


async def delete_survey_mission(
    survey_mission_id: identifiers.SurveyMissionId,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id!r} does not exist."
        )
    if not permissions.can_delete_survey_mission(initiator, survey_mission):
        raise errors.SeisLabDataError("User is not allowed to delete survey missions.")
    if survey_mission.status != SurveyMissionStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission with status {survey_mission.status}"
        )
    if survey_mission.project.status != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission because parent project's status "
            f"is {survey_mission.project.status}"
        )
    await commands.delete_survey_mission(session, survey_mission_id)
    await event_dispatcher(
        event_schemas.SurveyMissionDeletedEvent(
            survey_mission_id=survey_mission_id,
            initiator=initiator.id,
        )
    )


async def list_survey_missions(
    session: AsyncSession,
    initiator: user_schemas.User | None,
    project_id: identifiers.ProjectId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: filter_schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.SurveyMission], int | None]:
    kwargs = dict(
        project_id=project_id,
        page=page,
        page_size=page_size,
        include_total=include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
        temporal_extent=temporal_extent,
    )
    if initiator is None:
        return await queries.list_published_survey_missions(session, **kwargs)
    elif not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(initiator.roles):
        return await queries.list_survey_missions(session, **kwargs)
    else:
        return await queries.list_accessible_survey_missions(
            session, initiator.id, **kwargs
        )


async def get_survey_mission(
    survey_mission_id: identifiers.SurveyMissionId,
    initiator: user_schemas.User | None,
    session: AsyncSession,
) -> models.SurveyMission | None:
    mission = await queries.get_survey_mission(session, survey_mission_id)
    if mission is None:
        return None
    if not permissions.can_read_survey_mission(initiator, mission):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey mission {survey_mission_id!r}."
        )
    return mission
