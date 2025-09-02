import logging
import uuid

from .. import (
    config,
    schemas,
)


logger = logging.getLogger(__name__)


async def can_create_dataset_category(
    user: schemas.UserId,
    to_create: schemas.DatasetCategoryCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_dataset_category(
    user: schemas.UserId,
    dataset_category_id: uuid.UUID,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_create_domain_type(
    user: schemas.UserId,
    to_create: schemas.DomainTypeCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_domain_type(
    user: schemas.UserId,
    domain_type_id: uuid.UUID,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_create_workflow_stage(
    user: schemas.UserId,
    to_create: schemas.WorkflowStageCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_workflow_stage(
    user: schemas.UserId,
    workflow_stage_id: uuid.UUID,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_read_survey_related_record(
    user: schemas.UserId,
    survey_related_record_slug: str,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_create_survey_related_record(
    user: schemas.UserId,
    to_create: schemas.SurveyRelatedRecordCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_survey_related_record(
    user: schemas.UserId,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    *,
    settings: config.SeisLabDataSettings,
):
    return True
