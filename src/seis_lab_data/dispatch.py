import logging
from typing import Protocol

from redis import asyncio as aioredis

from . import constants
from .schemas import (
    events,
    messages,
)

logger = logging.getLogger(__name__)


class EventDispatcherProtocol(Protocol):
    async def __call__(self, event: events.SeisLabDataEvent) -> None: ...


async def no_op_dispatcher(event: events.SeisLabDataEvent) -> None:
    logger.debug(f"no-op dispatch called with {event=}")


class RedisEventDispatcher:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def __call__(self, event: events.SeisLabDataEvent) -> None:
        match event:
            case events.AssetDiscoveryConfigurationCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
                    messages.AssetDiscoveryConfigurationCreatedMessage(
                        asset_discovery_configuration_id=event.asset_discovery_configuration_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.AssetDiscoveryConfigurationNotCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
                    messages.AssetDiscoveryConfigurationNotCreatedMessage(
                        request_id=event.request_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.AssetDiscoveryConfigurationUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
                    messages.AssetDiscoveryConfigurationUpdatedMessage(
                        asset_discovery_configuration_id=event.asset_discovery_configuration_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.AssetDiscoveryConfigurationNotUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
                    messages.AssetDiscoveryConfigurationNotUpdatedMessage(
                        asset_discovery_configuration_id=event.asset_discovery_configuration_id,
                        request_id=event.request_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.AssetDiscoveryConfigurationDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
                    messages.AssetDiscoveryConfigurationDeletedMessage(
                        asset_discovery_configuration_id=event.asset_discovery_configuration_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.AssetDiscoveryConfigurationNotDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_ASSET_DISCOVERY_CONFIGURATIONS,
                    messages.AssetDiscoveryConfigurationNotDeletedMessage(
                        asset_discovery_configuration_id=event.asset_discovery_configuration_id,
                        request_id=event.request_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ProjectCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectCreatedMessage(
                        project_id=event.project_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.ProjectNotCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectNotCreatedMessage(
                        request_id=event.request_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ProjectUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectUpdatedMessage(
                        project_id=event.project_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.ProjectNotUpdatedEvent():
                logger.debug(f"{event=}")
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectNotUpdatedMessage(
                        project_id=event.project_id,
                        request_id=event.request_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ProjectDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectDeletedMessage(
                        project_id=event.project_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.ProjectStatusChangedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectStatusChangedMessage(
                        project_id=event.project_id,
                        new_status=event.new_status,
                    ).model_dump_json(),
                )
            case events.ProjectValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectValidatedMessage(
                        project_id=event.project_id,
                        is_valid=event.is_valid,
                    ).model_dump_json(),
                )
            case events.ProjectNotValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectNotValidatedMessage(
                        request_id=event.request_id,
                        project_id=event.project_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ProjectDiscoverySucceededEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectDiscoverySucceededMessage(
                        request_id=event.request_id, project_id=event.project_id
                    ).model_dump_json(),
                )
            case events.ProjectDiscoveryFailedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectDiscoveryFailedMessage(
                        request_id=event.request_id,
                        project_id=event.project_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.ProjectDiscoveryProgressEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_PROJECTS,
                    messages.ProjectDiscoveryProgressMessage(
                        project_id=event.project_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.SurveyMissionCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionCreatedMessage(
                        request_id=event.request_id,
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case events.SurveyMissionNotCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionNotCreatedMessage(
                        request_id=event.request_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.SurveyMissionUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionUpdatedMessage(
                        request_id=event.request_id,
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case events.SurveyMissionDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionDeletedMessage(
                        request_id=event.request_id,
                        survey_mission_id=event.survey_mission_id,
                        project_id=event.project_id,
                    ).model_dump_json(),
                )
            case events.SurveyMissionStatusChangedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionStatusChangedMessage(
                        survey_mission_id=event.survey_mission_id,
                        new_status=event.new_status,
                    ).model_dump_json(),
                )
            case events.SurveyMissionValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionValidatedMessage(
                        survey_mission_id=event.survey_mission_id,
                        is_valid=event.is_valid,
                    ).model_dump_json(),
                )
            case events.SurveyMissionDiscoveryProgressEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_MISSIONS,
                    messages.SurveyMissionDiscoveryProgressMessage(
                        survey_mission_id=event.survey_mission_id,
                        details=event.details,
                    ).model_dump_json(),
                )
            case events.SurveyRelatedRecordCreatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    messages.SurveyRelatedRecordCreatedMessage(
                        record_id=event.record_id,
                        survey_mission_id=event.survey_mission_id,
                        request_id=event.request_id,
                    ).model_dump_json(),
                )
            case events.SurveyRelatedRecordUpdatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    messages.SurveyRelatedRecordUpdatedMessage(
                        record_id=event.record_id,
                    ).model_dump_json(),
                )
            case events.SurveyRelatedRecordDeletedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    messages.SurveyRelatedRecordDeletedMessage(
                        request_id=event.request_id,
                        record_id=event.record_id,
                        survey_mission_id=event.survey_mission_id,
                    ).model_dump_json(),
                )
            case events.SurveyRelatedRecordStatusChangedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    messages.SurveyRelatedRecordStatusChangedMessage(
                        record_id=event.record_id,
                        new_status=event.new_status,
                    ).model_dump_json(),
                )
            case events.SurveyRelatedRecordValidatedEvent():
                await self._redis.publish(
                    constants.NEW_TOPIC_SURVEY_RELATED_RECORDS,
                    messages.SurveyRelatedRecordValidatedMessage(
                        record_id=event.record_id,
                        is_valid=event.is_valid,
                    ).model_dump_json(),
                )
            case _:
                logger.debug(f"no Redis dispatch configured for {event=}")
