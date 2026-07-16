import logging

from ..schemas.user import User
from ..constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SYSTEM_ADMIN,
    SurveyRelatedRecordStatus,
)
from ..db import models

logger = logging.getLogger(__name__)


def can_read_survey_related_record(
    user: User | None,
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
    user: User | None,
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
    user: User | None,
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
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_update_survey_related_record(user, record)


def can_validate_survey_related_record(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_update_survey_related_record(user, record)


def can_change_survey_related_record_status(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_update_survey_related_record(user, record)


def can_bulk_update_survey_related_records(user: User) -> bool:
    """Coarse-grained gate for attempting a bulk update.

    Mirrors the role check in `can_update_survey_related_record`. Unlike
    that function, this cannot also check per-record ownership, since bulk
    updates are deliberately implemented without loading each record.
    Ownership is instead enforced by scoping the underlying DB query to
    owned records (or, for admins, leaving it unrestricted).
    """
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    return ROLE_EDITOR in user.roles
