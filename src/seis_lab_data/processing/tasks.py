import asyncio
import json
import logging
import uuid

import dramatiq
from redis.asyncio import Redis

from .. import (
    config,
    constants,
    errors,
    schemas,
    operations,
)
from ..schemas import (
    identifiers,
    messages as message_schemas,
)

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
async def validate_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    survey_mission_id = identifiers.SurveyMissionId(uuid.UUID(raw_survey_mission_id))
    initiator = schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        try:
            await operations.validate_survey_mission(
                survey_mission_id, initiator, session, settings.get_event_dispatcher()
            )
        except Exception:
            logger.exception("Task failed")


@dramatiq.actor
@decorators.sld_settings
async def validate_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    initiator = schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        try:
            await operations.validate_project(
                project_id, initiator, session, settings.get_event_dispatcher()
            )
        except Exception:
            logger.exception("Task failed")


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def succinct_create_project(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
) -> None:
    topic_name = constants.NEW_TOPIC_PROJECTS
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    to_create = schemas.ProjectCreate.model_validate_json(raw_to_create)
    initiator = schemas.User(**json.loads(raw_initiator))
    await redis_client.publish(
        topic_name,
        message_schemas.ProjectCreationStartedMessage(
            request_id=request_id
        ).model_dump_json(),
    )
    try:
        async with settings.get_db_session_maker()() as session:
            project = await operations.create_project(
                to_create=to_create,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
    except errors.SeisLabDataError as err:
        await redis_client.publish(
            topic_name,
            message_schemas.ProjectCreationFailedMessage(
                request_id=request_id, details=str(err)
            ).model_dump_json(),
        )
    else:
        await redis_client.publish(
            topic_name,
            message_schemas.ProjectCreationSuccessfulMessage(
                request_id=request_id,
                project_id=identifiers.ProjectId(project.id),
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def succinct_update_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
) -> None:
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    topic_name = constants.NEW_TOPIC_PROJECTS
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.ProjectUpdate.model_validate_json(raw_to_update)
    await redis_client.publish(
        topic_name,
        message_schemas.ProjectUpdateStartedMessage(
            request_id=request_id,
            project_id=project_id,
        ).model_dump_json(),
    )
    try:
        async with settings.get_db_session_maker()() as session:
            await operations.update_project(
                project_id=project_id,
                to_update=to_update,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
    except errors.SeisLabDataError as err:
        await redis_client.publish(
            topic_name,
            message_schemas.ProjectUpdateFailedMessage(
                request_id=request_id,
                project_id=project_id,
                details=str(err),
            ).model_dump_json(),
        )
    else:
        await redis_client.publish(
            topic_name,
            message_schemas.ProjectUpdateSuccessfulMessage(
                request_id=request_id,
                project_id=project_id,
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def succinct_delete_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
) -> None:
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    topic_name = constants.NEW_TOPIC_PROJECTS
    initiator = schemas.User(**json.loads(raw_initiator))
    await redis_client.publish(
        topic_name,
        message_schemas.ProjectDeletionStartedMessage(
            request_id=request_id,
            project_id=project_id,
        ).model_dump_json(),
    )
    try:
        async with settings.get_db_session_maker()() as session:
            await operations.delete_project(
                project_id=project_id,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
    except errors.SeisLabDataError as err:
        await redis_client.publish(
            topic_name,
            message_schemas.ProjectDeletionFailedMessage(
                request_id=request_id,
                project_id=project_id,
                details=str(err),
            ).model_dump_json(),
        )
    else:
        await redis_client.publish(
            topic_name,
            message_schemas.ProjectDeletionSuccessfulMessage(
                request_id=request_id,
                project_id=project_id,
            ).model_dump_json(),
        )


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
async def create_project(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the create_project task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    to_create = schemas.ProjectCreate(**json.loads(raw_to_create))
    initiator = schemas.User(**json.loads(raw_initiator))
    logger.info(f"{to_create=}")
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Project creation started",
            ).model_dump_json(),
        )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Creating project...",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            project = await operations.create_project(
                to_create=to_create,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )

        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
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
                    status=constants.ProcessingStatus.RUNNING,
                    message=f"Project is being validated {i}...",
                ).model_dump_json(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.SUCCESS,
                message="Project successfully created",
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
async def update_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the update_project task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.ProjectUpdate(**json.loads(raw_to_update))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Project update started",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            await operations.update_project(
                project_id=identifiers.ProjectId(uuid.UUID(raw_project_id)),
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
                message="Project successfully updated",
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
async def delete_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the delete_project task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    initiator = schemas.User(**json.loads(raw_initiator))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Project deletion started",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            await operations.delete_project(
                project_id=project_id,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.SUCCESS,
                message="Project successfully deleted",
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
async def create_survey_mission(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    to_create = schemas.SurveyMissionCreate(**json.loads(raw_to_create))
    initiator = schemas.User(**json.loads(raw_initiator))
    logger.info(f"{to_create=}")
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Survey mission creation started",
            ).model_dump_json(),
        )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Creating survey mission...",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            survey_mission = await operations.create_survey_mission(
                to_create=to_create,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )

        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
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
                    status=constants.ProcessingStatus.RUNNING,
                    message=f"Survey mission is being validated {i}...",
                ).model_dump_json(),
            )
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.SUCCESS,
                message="Survey mission successfully created",
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
async def update_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the update_survey_mission task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    initiator = schemas.User(**json.loads(raw_initiator))
    to_update = schemas.SurveyMissionUpdate(**json.loads(raw_to_update))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Survey mission update started",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            await operations.update_survey_mission(
                survey_mission_id=identifiers.SurveyMissionId(
                    uuid.UUID(raw_survey_mission_id)
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
                message="Survey mission successfully updated",
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
async def delete_survey_mission(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
):
    logger.debug("Hi from the delete_survey_mission task")
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    topic_name = constants.PROGRESS_TOPIC_NAME_TEMPLATE.format(request_id=request_id)
    initiator = schemas.User(**json.loads(raw_initiator))
    try:
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=constants.ProcessingStatus.RUNNING,
                message="Survey mission deletion started",
            ).model_dump_json(),
        )
        async with settings.get_db_session_maker()() as session:
            await operations.delete_survey_mission(
                survey_mission_id=identifiers.SurveyMissionId(
                    uuid.UUID(raw_survey_mission_id)
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
                message="Survey mission successfully deleted",
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
