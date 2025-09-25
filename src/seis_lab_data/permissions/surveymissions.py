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
):
    return True


async def can_create_survey_mission(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
):
    # allow if user is admin
    # or if user is the owner of the parent campaign
    return True


async def can_delete_survey_mission(
    user: schemas.User,
    survey_mission_id: schemas.SurveyMissionId,
    *,
    settings: config.SeisLabDataSettings,
):
    return True
