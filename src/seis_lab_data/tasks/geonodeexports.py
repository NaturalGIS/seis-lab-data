import json
import logging
import uuid

import dramatiq

from .. import (
    config,
    constants,
)
from ..operations import geonodeexports as export_ops
from ..schemas import (
    identifiers,
    user as user_schemas,
)
from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)
logger = logging.getLogger(__name__)


# Own queue, so long uploads never delay the interactive tasks; no retries, as
# a failed export is to be retried by the user, who gets told of the failure
@dramatiq.actor(
    queue_name="exports",
    max_retries=0,
    time_limit=constants.GEONODE_EXPORT_TIME_LIMIT_SECONDS * 1000,
)
@decorators.sld_settings
async def export_survey_related_record_to_geonode(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    async with settings.get_db_session_maker()() as session:
        # recovering here as well as at worker boot means a stuck record gets
        # unstuck the next time anyone exports anything
        await export_ops.recover_stale_geonode_exports(
            request_id=request_id,
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
        await export_ops.export_survey_related_record(
            request_id=request_id,
            survey_related_record_id=identifiers.SurveyRelatedRecordId(
                uuid.UUID(raw_survey_related_record_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            settings=settings,
        )


@dramatiq.actor(queue_name="exports", max_retries=0, time_limit=60_000)
@decorators.sld_settings
async def recover_stale_geonode_exports(
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await export_ops.recover_stale_geonode_exports(
            request_id=identifiers.RequestId(uuid.uuid4()),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
