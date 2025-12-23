import logging

import pydantic
import shapely
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
    events,
)
from ..constants import (
    ProjectStatus,
    SurveyMissionStatus,
)
from ..db import (
    commands,
    queries,
    models,
)
from .. import (
    permissions,
    schemas,
)

logger = logging.getLogger(__name__)


async def create_survey_mission(
    to_create: schemas.SurveyMissionCreate,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
):
    if not (project := await queries.get_project(session, to_create.project_id)):
        raise errors.SeisLabDataError(
            f"Project with id {to_create.project_id} does not exist"
        )
    if initiator is None or not await permissions.can_create_survey_mission(
        initiator, schemas.ProjectId(to_create.project_id), settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to create a survey mission.")
    if (project_status := project.status) != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot create survey mission because parent project's "
            f"status is {project_status}"
        )
    survey_mission = await commands.create_survey_mission(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_CREATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                after=schemas.SurveyMissionReadDetail.from_db_instance(
                    survey_mission
                ).model_dump()
            ),
        )
    )
    return survey_mission


async def change_survey_mission_status(
    target_status: SurveyMissionStatus,
    survey_mission_id: schemas.SurveyMissionId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.SurveyMission:
    if initiator is None or not await permissions.can_change_survey_mission_status(
        initiator, survey_mission_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to change survey mission status."
        )
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id} does not exist."
        )
    if (old_status := survey_mission.status) == target_status:
        logger.info(
            f"Survey mission status is already set to {target_status} - nothing to do"
        )
        return survey_mission
    else:
        updated_survey_mission = await commands.set_survey_mission_status(
            session, schemas.SurveyMissionId(survey_mission.id), target_status
        )
        event_emitter(
            schemas.SeisLabDataEvent(
                type_=schemas.EventType.SURVEY_MISSION_STATUS_CHANGED,
                initiator=initiator.id,
                payload=schemas.EventPayload(
                    before={"status": old_status.value},
                    after={"status": updated_survey_mission.status.value},
                ),
            )
        )
        return updated_survey_mission


async def validate_survey_mission(
    survey_mission_id: schemas.SurveyMissionId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.SurveyMission:
    if initiator is None or not await permissions.can_validate_survey_mission(
        initiator, survey_mission_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to validate survey mission.")
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id} does not exist."
        )

    old_validation_result = survey_mission.validation_result or {
        "is_valid": False,
        "errors": None,
    }
    validation_errors = []
    try:
        schemas.ValidSurveyMission(**survey_mission.model_dump())
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
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_VALIDATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                before={
                    "survey_mission_id": survey_mission.id,
                    "validation_result": {**old_validation_result},
                },
                after={
                    "survey_mission_id": survey_mission.id,
                    "validation_result": {**survey_mission.validation_result},
                },
            ),
        )
    )
    return survey_mission


async def update_survey_mission(
    survey_mission_id: schemas.SurveyMissionId,
    to_update: schemas.SurveyMissionUpdate,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.SurveyMission:
    if initiator is None or not await permissions.can_update_survey_mission(
        initiator, survey_mission_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to update survey mission.")
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id} does not exist."
        )
    if survey_mission.status != SurveyMissionStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission with status {survey_mission.status}"
        )
    if survey_mission.project.status != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission because parent project's status "
            f"is {survey_mission.project.status}"
        )
    serialized_mission_before = schemas.SurveyMissionReadDetail.from_db_instance(
        survey_mission
    ).model_dump()
    updated_survey_mission = await commands.update_survey_mission(
        session, survey_mission, to_update
    )

    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_UPDATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                before=serialized_mission_before,
                after=schemas.SurveyMissionReadDetail.from_db_instance(
                    updated_survey_mission
                ).model_dump(),
            ),
        )
    )
    return updated_survey_mission


async def delete_survey_mission(
    survey_mission_id: schemas.SurveyMissionId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_survey_mission(
        initiator, survey_mission_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to delete survey missions.")
    if (
        survey_mission := await queries.get_survey_mission(session, survey_mission_id)
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey mission with id {survey_mission_id!r} does not exist."
        )
    if survey_mission.status != SurveyMissionStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission with status {survey_mission.status}"
        )
    if survey_mission.project.status != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete survey mission because parent project's status "
            f"is {survey_mission.project.status}"
        )
    serialized_survey_mission = schemas.SurveyMissionReadDetail.from_db_instance(
        survey_mission
    ).model_dump()
    await commands.delete_survey_mission(session, survey_mission_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_DELETED,
            initiator=initiator.id,
            payload=schemas.EventPayload(before=serialized_survey_mission),
        )
    )


async def list_survey_missions(
    session: AsyncSession,
    initiator: schemas.UserId | None,
    project_id: schemas.ProjectId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.SurveyMission], int | None]:
    return await queries.paginated_list_survey_missions(
        session,
        initiator,
        project_id=project_id,
        page=page,
        page_size=page_size,
        include_total=include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
        temporal_extent=temporal_extent,
    )


async def get_survey_mission(
    survey_mission_id: schemas.SurveyMissionId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> models.SurveyMission | None:
    if not await permissions.can_read_survey_mission(
        initiator, survey_mission_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey mission {survey_mission_id!r}."
        )
    return await queries.get_survey_mission(session, survey_mission_id)
