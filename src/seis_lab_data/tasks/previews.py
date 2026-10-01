import json
import logging
import uuid

import dramatiq

from .. import config
from ..operations import previews as preview_ops
from ..schemas import (
    identifiers,
    user as user_schemas,
)
from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)
logger = logging.getLogger(__name__)


# Own queue, so slow renders never delay the interactive tasks; a longer time
# limit, as a whole mission can need more than the 10 minute default;
# no retries, as the next discovery re-derives whatever is still missing.
@dramatiq.actor(queue_name="previews", max_retries=0, time_limit=1_800_000)
@decorators.sld_settings
async def generate_mission_previews(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await preview_ops.generate_mission_previews(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_mission_id=identifiers.SurveyMissionId(
                uuid.UUID(raw_survey_mission_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            settings=settings,
        )
