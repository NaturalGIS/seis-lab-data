import json
import logging
import uuid

import dramatiq
from redis.asyncio import Redis

from .. import (
    config,
    constants,
    errors,
)
from ..schemas import (
    events as event_schemas,
    processing as processing_schemas,
    identifiers,
    user as user_schemas,
)
from ..operations import (
    discovery as discovery_ops,
    projects as project_ops,
    surveymissions as survey_mission_ops,
)
from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)
logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def discover_project_contents(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    project_status_topic = constants.PROJECT_STATUS_CHANGED_TOPIC.format(
        project_id=project_id
    )
    project_discovery_topic = constants.PROJECT_DISCOVERY_TOPIC.format(
        project_id=project_id
    )
    initiator = user_schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        try:
            if (await project_ops.get_project(project_id, initiator, session)) is None:
                raise errors.SeisLabDataError(
                    f"Project with id {project_id!r} does not exist"
                )
            db_project = await project_ops.change_project_status(
                constants.ProjectStatus.UNDER_DISCOVERY,
                project_id,
                initiator=initiator,
                session=session,
                event_emitter=settings.get_event_emitter(),
            )
            await redis_client.publish(
                project_status_topic,
                processing_schemas.ProjectEvent(
                    project_id=project_id,
                    event=event_schemas.EventType.PROJECT_DISCOVERY_STARTED,
                ).model_dump_json(),
            )

            async for (
                db_survey_mission
            ) in discovery_ops.discover_project_survey_missions(
                session=session,
                project=db_project,
                event_emitter=settings.get_event_emitter(),
                settings=settings,
                user=initiator,
            ):
                survey_mission_id = identifiers.SurveyMissionId(db_survey_mission.id)
                mission_status_topic = (
                    constants.SURVEY_MISSION_STATUS_CHANGED_TOPIC.format(
                        survey_mission_id=survey_mission_id
                    )
                )
                await redis_client.publish(
                    project_discovery_topic,
                    processing_schemas.ProjectEvent(
                        project_id=project_id,
                        event=event_schemas.EventType.SURVEY_MISSION_CREATED,
                    ).model_dump_json(),
                )
                await redis_client.publish(
                    constants.SURVEY_MISSION_CREATED_TOPIC,
                    processing_schemas.SurveyMissionEvent(
                        survey_mission_id=survey_mission_id,
                        event=event_schemas.EventType.SURVEY_MISSION_CREATED,
                    ).model_dump_json(),
                )

                await survey_mission_ops.change_survey_mission_status(
                    constants.SurveyMissionStatus.UNDER_DISCOVERY,
                    survey_mission_id,
                    initiator,
                    session,
                    event_emitter=settings.get_event_emitter(),
                )
                await redis_client.publish(
                    mission_status_topic,
                    processing_schemas.SurveyMissionEvent(
                        survey_mission_id=survey_mission_id,
                        event=event_schemas.EventType.SURVEY_MISSION_STATUS_CHANGED,
                    ).model_dump_json(),
                )

                async for db_record in discovery_ops.discover_survey_mission_records(
                    session=session,
                    archive_root=str(settings.readonly_archive_root_directory),
                    survey_mission=db_survey_mission,
                    event_emitter=settings.get_event_emitter(),
                    user=initiator,
                ):
                    record_id = identifiers.SurveyRelatedRecordId(db_record.id)
                    await redis_client.publish(
                        constants.SURVEY_MISSION_DISCOVERY_TOPIC.format(
                            survey_mission_id=survey_mission_id
                        ),
                        processing_schemas.SurveyMissionEvent(
                            survey_mission_id=survey_mission_id,
                            event=event_schemas.EventType.SURVEY_RELATED_RECORD_CREATED,
                        ).model_dump_json(),
                    )
                    await redis_client.publish(
                        constants.SURVEY_RELATED_RECORD_CREATED_TOPIC,
                        processing_schemas.SurveyRelatedRecordEvent(
                            survey_related_record_id=record_id,
                            event=event_schemas.EventType.SURVEY_RELATED_RECORD_CREATED,
                        ).model_dump_json(),
                    )

                await survey_mission_ops.change_survey_mission_status(
                    constants.SurveyMissionStatus.DRAFT,
                    survey_mission_id,
                    initiator,
                    session,
                    event_emitter=settings.get_event_emitter(),
                )
                await redis_client.publish(
                    mission_status_topic,
                    processing_schemas.SurveyMissionEvent(
                        survey_mission_id=survey_mission_id,
                        event=event_schemas.EventType.SURVEY_MISSION_STATUS_CHANGED,
                    ).model_dump_json(),
                )

            await project_ops.change_project_status(
                constants.ProjectStatus.DRAFT,
                project_id,
                initiator=initiator,
                session=session,
                event_emitter=settings.get_event_emitter(),
            )
            await redis_client.publish(
                project_status_topic,
                processing_schemas.ProjectEvent(
                    project_id=project_id,
                    event=event_schemas.EventType.PROJECT_DISCOVERY_FINISHED,
                ).model_dump_json(),
            )
        except Exception:
            logger.exception("Task failed")
