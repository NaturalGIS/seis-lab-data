import logging

from ..schemas.user import User
from ..db import models

from .common import can_manage_item

logger = logging.getLogger(__name__)


def can_read_private_survey_mission(
    user: User | None,
    mission: models.SurveyMission,
) -> bool:
    return user is not None


def can_create_survey_mission(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_manage_item(user)


def can_update_survey_mission(
    user: User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_manage_item(user)


def can_delete_survey_mission(
    user: User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_manage_item(user)


def can_validate_survey_mission(
    user: User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_manage_item(user)


def can_discover_survey_mission(user: User, mission: models.SurveyMission) -> bool:
    return can_manage_item(user)


def can_change_survey_mission_status(
    user: User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_manage_item(user)
