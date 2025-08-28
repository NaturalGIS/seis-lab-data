import logging
from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


async def can_create_survey_mission(
    user_id: str,
    group: str,
    to_create: schemas.SurveyMissionCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    # allow if user is admin
    # or if user is the owner of the parent campaign
    return True
