import logging

from ..schemas.user import User
from ..db import models
from .common import can_manage_item

logger = logging.getLogger(__name__)


def can_read_private_survey_related_record(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return user is not None


def can_create_survey_related_record(
    user: User | None,
    mission: models.SurveyMission,
) -> bool:
    return can_manage_item(user)


def can_update_survey_related_record(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_manage_item(user)


def can_delete_survey_related_record(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_manage_item(user)


def can_validate_survey_related_record(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_manage_item(user)


def can_change_survey_related_record_status(
    user: User | None,
    record: models.SurveyRelatedRecord,
) -> bool:
    return can_manage_item(user)


def can_bulk_update_survey_related_records(user: User) -> bool:
    """Coarse-grained gate for attempting a bulk update."""
    return can_manage_item(user)
