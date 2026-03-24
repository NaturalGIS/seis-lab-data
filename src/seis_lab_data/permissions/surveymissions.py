import logging

from .. import (
    config,
    schemas,
)
from ..constants import ROLE_ADMIN, SurveyMissionStatus
from ..db import models

logger = logging.getLogger(__name__)


def _is_admin(user: schemas.User) -> bool:
    return ROLE_ADMIN in user.roles


def can_read_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is not None and _is_admin(user):
        return True
    if mission.status == SurveyMissionStatus.PUBLISHED:
        return True
    return user is not None and (
        mission.owner == user.id or mission.project.owner == user.id
    )


def can_create_survey_mission(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return _is_admin(user) or project.owner == user.id


def can_delete_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return (
        _is_admin(user) or mission.owner == user.id or mission.project.owner == user.id
    )


def can_update_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return (
        _is_admin(user) or mission.owner == user.id or mission.project.owner == user.id
    )


def can_validate_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_survey_mission(user, mission, settings)


def can_change_survey_mission_status(
    user: schemas.User | None,
    mission: models.SurveyMission,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_survey_mission(user, mission, settings)
