import logging

from .. import schemas
from ..constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SYSTEM_ADMIN,
    SurveyMissionStatus,
)
from ..db import models

logger = logging.getLogger(__name__)


def can_read_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
) -> bool:
    if user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if mission.status == SurveyMissionStatus.PUBLISHED:
        return True
    return user and (mission.owner_id == user.id or mission.project.owner_id == user.id)


def can_create_survey_mission(
    user: schemas.User | None,
    project: models.Project,
) -> bool:
    if user is None:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    return ROLE_EDITOR in user.roles and project.owner_id == user.id


def can_update_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
) -> bool:
    if not user:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if ROLE_EDITOR in user.roles and mission.owner_id == user.id:
        return True
    if ROLE_EDITOR in user.roles and mission.project.owner_id == user.id:
        return True
    return False


def can_delete_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_update_survey_mission(user, mission)


def can_validate_survey_mission(
    user: schemas.User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_update_survey_mission(user, mission)


def can_change_survey_mission_status(
    user: schemas.User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_update_survey_mission(user, mission)
