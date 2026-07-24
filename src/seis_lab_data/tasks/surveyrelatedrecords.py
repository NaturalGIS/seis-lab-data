import json
import logging
import uuid

import dramatiq

from .. import (
    config,
    constants,
)
from ..operations import surveyrelatedrecords as record_ops
from ..schemas import (
    identifiers,
    surveyrelatedrecords as record_schemas,
    user as user_schemas,
)

from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)

logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def create_survey_related_record(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    async with settings.get_db_session_maker()() as session:
        await record_ops.create_survey_related_record(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_create=record_schemas.SurveyRelatedRecordCreate.model_validate_json(
                raw_to_create
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def delete_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    async with settings.get_db_session_maker()() as session:
        await record_ops.delete_survey_related_record(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_related_record_id=identifiers.SurveyRelatedRecordId(
                uuid.UUID(raw_survey_related_record_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def update_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    async with settings.get_db_session_maker()() as session:
        await record_ops.update_survey_related_record(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_related_record_id=identifiers.SurveyRelatedRecordId(
                uuid.UUID(raw_survey_related_record_id)
            ),
            to_update=record_schemas.SurveyRelatedRecordUpdate.model_validate_json(
                raw_to_update
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def handle_survey_related_record_publication(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    publishing_info = record_schemas.SurveyRelatedRecordPublication.model_validate_json(
        raw_to_update
    )
    async with settings.get_db_session_maker()() as session:
        await record_ops.change_survey_related_record_status(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            target_status=(
                constants.SurveyRelatedRecordStatus.PUBLISHED
                if publishing_info.published
                else constants.SurveyRelatedRecordStatus.DRAFT
            ),
            survey_related_record_id=identifiers.SurveyRelatedRecordId(
                uuid.UUID(raw_survey_related_record_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def bulk_update_survey_related_records(
    raw_request_id: str,
    raw_to_update: str,
    raw_selection: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    selection = (
        record_schemas.SurveyRelatedRecordBulkUpdateSelection.model_validate_json(
            raw_selection
        )
    )
    async with settings.get_db_session_maker()() as session:
        await record_ops.bulk_update_survey_related_records(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_update=record_schemas.SurveyRelatedRecordBulkUpdate.model_validate_json(
                raw_to_update
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            selected=selection.selected,
            excluded_record_ids=selection.excluded_record_ids,
            en_name_filter=selection.en_name_filter,
            pt_name_filter=selection.pt_name_filter,
            spatial_intersect=selection.spatial_intersect,
            temporal_extent=selection.temporal_extent,
            asset_path_fragment_filter=selection.asset_path_fragment_filter,
        )
