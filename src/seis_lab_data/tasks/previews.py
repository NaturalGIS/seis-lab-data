import json
import logging
import uuid

import dramatiq

from .. import config
from ..db.queries import (
    projects as project_queries,
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
)
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
        record_ids = await preview_ops.collect_survey_mission_records_missing_previews(
            session, identifiers.SurveyMissionId(uuid.UUID(raw_survey_mission_id))
        )
    for record_id in record_ids:
        generate_record_previews.send(
            raw_request_id=raw_request_id,
            raw_survey_related_record_id=str(record_id),
            raw_initiator=raw_initiator,
        )


# a single record renders in seconds, 10 minutes should work
@dramatiq.actor(queue_name="previews", max_retries=0, time_limit=600_000)
@decorators.sld_settings
async def generate_record_previews(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    record_id = identifiers.SurveyRelatedRecordId(
        uuid.UUID(raw_survey_related_record_id)
    )
    async with settings.get_db_session_maker()() as session:
        if (
            record := await record_queries.get_survey_related_record(session, record_id)
        ) is None:
            logger.warning(
                f"Survey-related record {record_id} no longer exists - not "
                f"generating its previews..."
            )
            return
        await preview_ops.generate_record_previews(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_related_record=record,
            directory_prefixes=await preview_ops.load_preview_directories(settings),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            settings=settings,
        )


# own queue, so a thumbnail never waits behind the previews of a whole discovery
@dramatiq.actor(queue_name="thumbnails", max_retries=0, time_limit=60_000)
@decorators.sld_settings
async def generate_project_thumbnail(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    async with settings.get_db_session_maker()() as session:
        if (project := await project_queries.get_project(session, project_id)) is None:
            logger.warning(
                f"Project {project_id} no longer exists - not generating its "
                f"thumbnail..."
            )
            return
        await preview_ops.generate_project_thumbnail(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            project=project,
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            settings=settings,
        )


@dramatiq.actor(queue_name="thumbnails", max_retries=0, time_limit=60_000)
@decorators.sld_settings
async def generate_survey_mission_thumbnail(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    survey_mission_id = identifiers.SurveyMissionId(uuid.UUID(raw_survey_mission_id))
    async with settings.get_db_session_maker()() as session:
        if (
            survey_mission := await mission_queries.get_survey_mission(
                session, survey_mission_id
            )
        ) is None:
            logger.warning(
                f"Survey mission {survey_mission_id} no longer exists - not "
                f"generating its thumbnail..."
            )
            return
        await preview_ops.generate_survey_mission_thumbnail(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            survey_mission=survey_mission,
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            settings=settings,
        )
