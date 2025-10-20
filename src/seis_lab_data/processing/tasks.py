import asyncio
import json
import logging
import uuid
from collections.abc import Callable

import dramatiq
from redis.asyncio import Redis
from dramatiq.brokers.stub import StubBroker

from .. import (
    config,
    schemas,
    operations,
)
from ..constants import ProcessingStatus

from ..events import get_event_emitter
from . import decorators

logger = logging.getLogger(__name__)

# this _stub_broker is only meant as a way to be able to register actors
# without triggering the unwanted side-effect of having dramatiq eagerly
# trying to connect to it
_stub_broker = StubBroker()
dramatiq.set_broker(_stub_broker)


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def create_project(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the create_project task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    to_create = schemas.ProjectCreate(**json.loads(raw_to_create))
    initiator = schemas.User(**json.loads(raw_initiator))
    logger.info(f"{to_create=}")
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Project creation started",
            ).model_dump_json(),
        )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Creating project...",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            project = await operations.create_project(
                to_create=to_create,
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )

        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message=f"Created project {project.id!r}",
            ).model_dump_json(),
        )

        # simulating some more work
        for i in range(3):
            await asyncio.sleep(1)
            await redis_client.publish(
                topic_name,
                schemas.ProcessingMessage(
                    request_id=request_id,
                    status=ProcessingStatus.RUNNING,
                    message=f"Project is being validated {i}...",
                ).model_dump_json(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Project successfully created",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.exception("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def update_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the update_project task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.ProjectUpdate(**json.loads(raw_to_update))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Project update started",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            await operations.update_project(
                project_id=schemas.ProjectId(uuid.UUID(raw_project_id)),
                to_update=to_update,
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Project successfully updated",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.exception("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def delete_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the delete_project task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    initiator = schemas.User(**json.loads(raw_initiator))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Project deletion started",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            await operations.delete_project(
                project_id=schemas.ProjectId(uuid.UUID(raw_project_id)),
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Project successfully deleted",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.error("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def create_survey_mission(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    to_create = schemas.SurveyMissionCreate(**json.loads(raw_to_create))
    initiator = schemas.User(**json.loads(raw_initiator))
    logger.info(f"{to_create=}")
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Survey mission creation started",
            ).model_dump_json(),
        )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Creating survey mission...",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            survey_mission = await operations.create_survey_mission(
                to_create=to_create,
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )

        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message=f"Created survey mission {survey_mission.id!r}",
            ).model_dump_json(),
        )

        # simulating some more work
        for i in range(3):
            await asyncio.sleep(1)
            await redis_client.publish(
                topic_name,
                schemas.ProcessingMessage(
                    request_id=request_id,
                    status=ProcessingStatus.RUNNING,
                    message=f"Survey mission is being validated {i}...",
                ).model_dump_json(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Survey mission successfully created",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.error("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def update_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the update_survey_mission task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.SurveyMissionUpdate(**json.loads(raw_to_update))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Survey mission update started",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            await operations.update_survey_mission(
                survey_mission_id=schemas.SurveyMissionId(
                    uuid.UUID(raw_survey_mission_id)
                ),
                to_update=to_update,
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Survey mission successfully updated",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.error("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def delete_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the delete_survey_mission task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    initiator = schemas.User(**json.loads(raw_initiator))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Survey mission deletion started",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            await operations.delete_survey_mission(
                survey_mission_id=schemas.SurveyMissionId(
                    uuid.UUID(raw_survey_mission_id)
                ),
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Survey mission successfully deleted",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.error("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def create_survey_related_record(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    to_create = schemas.SurveyRelatedRecordCreate(**json.loads(raw_to_create))
    initiator = schemas.User(**json.loads(raw_initiator))
    logger.info(f"{to_create=}")
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Survey-related record creation started",
            ).model_dump_json(),
        )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Creating survey-related record...",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            survey_related_record = await operations.create_survey_related_record(
                to_create=to_create,
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )

        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
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
                    status=ProcessingStatus.RUNNING,
                    message=f"Survey-related record is being validated {i}...",
                ).model_dump_json(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Survey-related record successfully created",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.error("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def delete_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the delete_survey_related_record task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    initiator = schemas.User(**json.loads(raw_initiator))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Survey-related record deletion started",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            await operations.delete_survey_related_record(
                survey_related_record_id=schemas.SurveyRelatedRecordId(
                    uuid.UUID(raw_survey_related_record_id)
                ),
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Survey-related record successfully deleted",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.error("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def update_survey_related_record(
    raw_request_id: str,
    raw_survey_related_record_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the update_survey_related_record task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.SurveyRelatedRecordUpdate(**json.loads(raw_to_update))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Survey-related record update started",
            ).model_dump_json(),
        )
        async with session_maker() as session:
            await operations.update_survey_related_record(
                survey_related_record_id=schemas.SurveyRelatedRecordId(
                    uuid.UUID(raw_survey_related_record_id)
                ),
                to_update=to_update,
                initiator=initiator,
                session=session,
                settings=settings,
                event_emitter=get_event_emitter(settings),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.SUCCESS,
                message="Survey-related record successfully updated",
            ).model_dump_json(),
        )
    except Exception as err:
        logger.exception("Task failed")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(err)
            ).model_dump_json(),
        )
