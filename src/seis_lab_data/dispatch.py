import logging
from typing import Protocol

from redis import asyncio as aioredis

from . import constants
from .schemas import events as event_schemas
from .schemas import messages as message_schemas

logger = logging.getLogger(__name__)


class EventDispatcherProtocol(Protocol):
    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None: ...


async def no_op_dispatcher(event: event_schemas.SeisLabDataEvent) -> None:
    logger.debug(f"no-op dispatch called with {event=}")


class RedisEventDispatcher:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        match event:
            case event_schemas.ProjectCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    message_schemas.ProjectCreatedMessage(
                        project_id=event.project_id,
                    ).model_dump_json(),
                )
            case event_schemas.ProjectUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    message_schemas.ProjectUpdatedMessage(
                        project_id=event.project_id,
                    ).model_dump_json(),
                )
            case event_schemas.ProjectDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    message_schemas.ProjectDeletedMessage(
                        project_id=event.project_id,
                    ).model_dump_json(),
                )
            case event_schemas.ProjectStatusChangedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    message_schemas.ProjectStatusChangedMessage(
                        project_id=event.project_id,
                        new_status=event.new_status,
                    ).model_dump_json(),
                )
            case event_schemas.ProjectValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    message_schemas.ProjectValidatedMessage(
                        project_id=event.project_id,
                        is_valid=event.is_valid,
                    ).model_dump_json(),
                )
            case event_schemas.ProjectDiscoveryProgressEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    message_schemas.ProjectDiscoveryProgressMessage(
                        project_id=event.project_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyMissionCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    message_schemas.SurveyMissionCreatedMessage(
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyMissionUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    message_schemas.SurveyMissionUpdatedMessage(
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyMissionDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    message_schemas.SurveyMissionDeletedMessage(
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyMissionStatusChangedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    message_schemas.SurveyMissionStatusChangedMessage(
                        survey_mission_id=event.survey_mission_id,
                        new_status=event.new_status,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyMissionValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    message_schemas.SurveyMissionValidatedMessage(
                        survey_mission_id=event.survey_mission_id,
                        is_valid=event.is_valid,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyMissionDiscoveryProgressEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    message_schemas.SurveyMissionDiscoveryProgressMessage(
                        survey_mission_id=event.survey_mission_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyRelatedRecordCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    message_schemas.SurveyRelatedRecordCreatedMessage(
                        record_id=event.record_id,
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyRelatedRecordUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    message_schemas.SurveyRelatedRecordUpdatedMessage(
                        record_id=event.record_id,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyRelatedRecordDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    message_schemas.SurveyRelatedRecordDeletedMessage(
                        record_id=event.record_id,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyRelatedRecordStatusChangedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    message_schemas.SurveyRelatedRecordStatusChangedMessage(
                        record_id=event.record_id,
                        new_status=event.new_status,
                    ).model_dump_json(),
                )
            case event_schemas.SurveyRelatedRecordValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    message_schemas.SurveyRelatedRecordValidatedMessage(
                        record_id=event.record_id,
                        is_valid=event.is_valid,
                    ).model_dump_json(),
                )
            case _:
                logger.debug(f"no Redis dispatch configured for {event=}")
