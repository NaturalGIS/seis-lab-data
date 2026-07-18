import json
import logging
import uuid

import dramatiq

from .. import config
from ..operations import surveymissions as survey_mission_ops
from ..schemas import (
    identifiers,
    surveymissions as survey_mission_schemas,
    user as user_schemas,
)
from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)
logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def create_survey_mission(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await survey_mission_ops.create_survey_mission(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_create=survey_mission_schemas.SurveyMissionCreate.model_validate_json(
                raw_to_create
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def update_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    async with settings.get_db_session_maker()() as session:
        await survey_mission_ops.update_survey_mission(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_mission_id=identifiers.SurveyMissionId(
                uuid.UUID(raw_survey_mission_id)
            ),
            to_update=survey_mission_schemas.SurveyMissionUpdate.model_validate_json(
                raw_to_update
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def delete_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    async with settings.get_db_session_maker()() as session:
        await survey_mission_ops.delete_survey_mission(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_mission_id=identifiers.SurveyMissionId(
                uuid.UUID(raw_survey_mission_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
