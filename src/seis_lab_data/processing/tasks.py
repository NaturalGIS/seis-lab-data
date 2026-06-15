import asyncio
import json
import logging
import uuid

import dramatiq
from redis.asyncio import Redis

from .. import (
    config,
    constants,
    schemas,
    operations,
)
from ..schemas import identifiers

from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)

logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def validate_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    survey_related_record_id = identifiers.SurveyRelatedRecordId(
        uuid.UUID(raw_survey_related_record_id)
    )
    initiator = schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        try:
            await operations.validate_survey_related_record(
                survey_related_record_id,
                initiator,
                session,
                settings.get_event_dispatcher(),
            )
        except Exception:
            logger.exception("Task failed")


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def create_survey_related_record(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    to_create = schemas.SurveyRelatedRecordCreate(**json.loads(raw_to_create))
    initiator = schemas.User(**json.loads(raw_initiator))
    logger.info(f"{to_create=}")
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Survey-related record creation started",
            ).model_dump_json(),
        )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Creating survey-related record...",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            survey_related_record = await operations.create_survey_related_record(
                to_create=to_create,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
                request_id=request_id,
            )

        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message=f"Created survey-related record {survey_related_record.id!r}",
            ).model_dump_json(),
        )

        # simulating some more work
        for i in range(3):
            await asyncio.sleep(1)
            await redis_client.publish(
                topic_name,
                schemas.ProcessingMessage(
                    request_id=request_id,
                    status=constants.ProcessingStatus.RUNNING,
                    message=f"Survey-related record is being validated {i}...",
                ).model_dump_json(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.SUCCESS,
                message="Survey-related record successfully created",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.exception("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.FAILED,
                message=str(err),
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def delete_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the delete_survey_related_record task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    initiator = schemas.User(**json.loads(raw_initiator))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Survey-related record deletion started",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            await operations.delete_survey_related_record(
                survey_related_record_id=identifiers.SurveyRelatedRecordId(
                    uuid.UUID(raw_survey_related_record_id)
                ),
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.SUCCESS,
                message="Survey-related record successfully deleted",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.exception("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.FAILED,
                message=str(err),
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def update_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the update_survey_related_record task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.SurveyRelatedRecordUpdate(**json.loads(raw_to_update))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Survey-related record update started",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            await operations.update_survey_related_record(
                survey_related_record_id=identifiers.SurveyRelatedRecordId(
                    uuid.UUID(raw_survey_related_record_id)
                ),
                to_update=to_update,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.SUCCESS,
                message="Survey-related record successfully updated",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.exception("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.FAILED,
                message=str(err),
            ).model_dump_json(),
        )
