import logging

from .. import schemas
from ..constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SYSTEM_ADMIN,
    SurveyRelatedRecordStatus,
)
from ..db import models

logger = logging.getLogger(__name__)


def can_create_dataset_category(
    user: schemas.User | None,
) -> bool:
    return user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_delete_dataset_category(
    user: schemas.User | None,
) -> bool:
    return user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_create_domain_type(
    user: schemas.User | None,
) -> bool:
    return user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_delete_domain_type(
    user: schemas.User | None,
) -> bool:
    return user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_create_workflow_stage(
    user: schemas.User | None,
) -> bool:
    return user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_delete_workflow_stage(
    user: schemas.User | None,
) -> bool:
    return user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_read_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    if user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if record.status == SurveyRelatedRecordStatus.PUBLISHED:
        return True
    if user and record.owner_id == user.id:
        return True
    if user and record.survey_mission.owner_id == user.id:
        return True
    if user and record.survey_mission.project.owner_id == user.id:
        return True
    return False


def can_create_survey_related_record(
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


def can_update_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    if not user:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if ROLE_EDITOR in user.roles and record.owner_id == user.id:
        return True
    if ROLE_EDITOR in user.roles and record.survey_mission.owner_id == user.id:
        return True
    if ROLE_EDITOR in user.roles and record.survey_mission.project.owner_id == user.id:
        return True
    return False


def can_delete_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_update_survey_related_record(user, record)


def can_validate_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_update_survey_related_record(user, record)


def can_change_survey_related_record_status(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_update_survey_related_record(user, record)
