import json
import logging
import uuid

import dramatiq

from .. import config
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
async def validate_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    async with settings.get_db_session_maker()() as session:
        await record_ops.validate_survey_related_record(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_related_record_id=identifiers.SurveyRelatedRecordId(
                uuid.UUID(raw_survey_related_record_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
