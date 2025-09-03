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


async def create_survey_mission(
    session: AsyncSession,
    to_create: schemas.SurveyMissionCreate,
) -> models.SurveyMission:
    survey_mission = models.SurveyMission(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(survey_mission)
    await session.commit()
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
