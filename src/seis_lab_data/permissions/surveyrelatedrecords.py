import logging

from .. import (
    config,
    schemas,
)
from ..constants import ADMIN_ROLE, SurveyRelatedRecordStatus
from ..db import models

logger = logging.getLogger(__name__)


def _is_admin(user: schemas.User) -> bool:
    return ADMIN_ROLE in user.roles


def can_create_dataset_category(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None and _is_admin(user)


def can_delete_dataset_category(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None and _is_admin(user)


def can_create_domain_type(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None and _is_admin(user)


def can_delete_domain_type(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None and _is_admin(user)


def can_create_workflow_stage(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None and _is_admin(user)


def can_delete_workflow_stage(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None and _is_admin(user)


def can_read_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is not None and _is_admin(user):
        return True
    if record.status == SurveyRelatedRecordStatus.PUBLISHED:
        return True
    return user is not None and (
        record.owner == user.id
        or record.survey_mission.owner == user.id
        or record.survey_mission.project.owner == user.id
    )


def can_create_survey_related_record(
    user: schemas.User | None,
    mission: models.SurveyMission,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return (
        _is_admin(user) or mission.owner == user.id or mission.project.owner == user.id
    )


def can_delete_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return (
        _is_admin(user)
        or record.owner == user.id
        or record.survey_mission.owner == user.id
        or record.survey_mission.project.owner == user.id
    )


def can_update_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return (
        _is_admin(user)
        or record.owner == user.id
        or record.survey_mission.owner == user.id
        or record.survey_mission.project.owner == user.id
    )


def can_validate_survey_related_record(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_survey_related_record(user, record, settings)


def can_change_survey_related_record_status(
    user: schemas.User | None,
    record: models.SurveyRelatedRecord,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_survey_related_record(user, record, settings)
