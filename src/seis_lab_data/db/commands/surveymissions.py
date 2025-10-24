import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import (
    errors,
    schemas,
)
from .. import (
    models,
    queries,
)
from .common import get_creation_bbox_4326

logger = logging.getLogger(__name__)


async def create_survey_mission(
    session: AsyncSession,
    to_create: schemas.SurveyMissionCreate,
) -> models.SurveyMission:
    survey_mission = models.SurveyMission(
        **to_create.model_dump(exclude={"bbox_4326"}),
        bbox_4326=(
            get_creation_bbox_4326(bbox)
            if (bbox := to_create.bbox_4326) is not None
            else bbox
        ),
    )
    # need to ensure english name is unique for combination of project and survey mission
    if await queries.get_survey_mission_by_english_name(
        session, schemas.ProjectId(to_create.project_id), to_create.name.en
    ):
        raise errors.SeisLabDataError(
            f"There is already a survey mission with english name {to_create.name.en!r} for "
            f"the same project."
        )

    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return await queries.get_survey_mission(session, to_create.id)


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


async def update_survey_mission(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    to_update: schemas.SurveyMissionUpdate,
) -> models.SurveyMission:
    logger.debug(f"{to_update.model_dump()=}")
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(survey_mission, key, value)
    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return survey_mission
