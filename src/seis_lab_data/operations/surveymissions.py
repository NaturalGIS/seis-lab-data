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
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
):
    if initiator is None or not await permissions.can_create_survey_mission(
        initiator, to_create, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to create a survey mission.")
    survey_mission = await commands.create_survey_mission(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_CREATED,
            initiator=initiator,
            payload=schemas.EventPayload(
                after=schemas.SurveyMissionReadDetail(
                    **survey_mission.model_dump()
                ).model_dump()
            ),
        )
    )
    return survey_mission


async def delete_survey_mission(
    survey_mission_id: schemas.SurveyMissionId,
    initiator: schemas.UserId | None,
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
    serialized_survey_mission = schemas.SurveyMissionReadDetail(
        **survey_mission.model_dump()
    ).model_dump()
    await commands.delete_survey_mission(session, survey_mission_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.SURVEY_MISSION_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_survey_mission),
        )
    )


async def list_survey_missions(
    session: AsyncSession,
    initiator: schemas.UserId | None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.SurveyMission], int | None]:
    return await queries.list_survey_missions(
        session, initiator, limit, offset, include_total
    )


async def get_survey_mission_by_slug(
    survey_mission_slug: str,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> models.SurveyMission | None:
    if not permissions.can_read_survey_mission(
        initiator, survey_mission_slug, settings=settings
    ):
        raise errors.SeisLabDataError(
            f"User is not allowed to read survey mission {survey_mission_slug!r}."
        )
    return await queries.get_survey_mission_by_slug(session, survey_mission_slug)
