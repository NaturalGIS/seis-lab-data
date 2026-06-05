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
    discovery_topic = constants.PROJECT_DISCOVERY_TOPIC.format(project_id=project_id)
    status_topic = constants.PROJECT_STATUS_CHANGED_TOPIC.format(project_id=project_id)
    logger.debug(f"discovery updates will be published to topic {discovery_topic=} ")
    logger.debug(f"status updates will be published to topic {status_topic=} ")
    initiator = user_schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        try:
            await redis_client.publish(
                status_topic,
                processing_schemas.ProjectEvent(
                    project_id=project_id,
                    event=event_schemas.EventType.PROJECT_DISCOVERY_STARTED,
                ).model_dump_json(),
            )
            await asyncio.sleep(2)
            if (
                db_project := await project_ops.get_project(
                    project_id, initiator, session
                )
            ) is None:
                raise errors.SeisLabDataError(
                    f"Project with id {project_id!r} does not exist"
                )
            await discovery_ops.discover_project_contents(
                session=session, project=db_project, settings=settings, user=initiator
            )
            await redis_client.publish(
                status_topic,
                processing_schemas.ProjectEvent(
                    project_id=project_id,
                    event=event_schemas.EventType.PROJECT_DISCOVERY_FINISHED,
                ).model_dump_json(),
            )
            await asyncio.sleep(2)
        except Exception:
            logger.exception("Task failed")
