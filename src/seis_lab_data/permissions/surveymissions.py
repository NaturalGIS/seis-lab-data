import logging

from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


async def can_read_survey_mission(
    user: schemas.User,
    survey_mission_id: schemas.SurveyMissionId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_create_survey_mission(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    # allow if user is admin
    # or if user is the owner of the parent campaign
    return True


async def can_delete_survey_mission(
    user: schemas.User,
    survey_mission_id: schemas.SurveyMissionId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_update_survey_mission(
    user: schemas.User,
    survey_mission_id: schemas.SurveyMissionId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_validate_survey_mission(
    user: schemas.User,
    survey_mission_id: schemas.SurveyMissionId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return await can_update_survey_mission(user, survey_mission_id, settings=settings)
