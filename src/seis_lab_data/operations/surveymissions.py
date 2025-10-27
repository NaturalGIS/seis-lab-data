import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
    events,
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
    if initiator is None or not await permissions.can_create_survey_mission(
        initiator, schemas.ProjectId(to_create.project_id), settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to create a survey mission.")
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
    )


async def get_survey_mission(
    survey_mission_id: schemas.SurveyMissionId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> models.SurveyMission | None:
    if not permissions.can_read_survey_mission(
        initiator, survey_mission_id, settings=settings
    ):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey mission {survey_mission_id!r}."
        )
    return await queries.get_survey_mission(session, survey_mission_id)
