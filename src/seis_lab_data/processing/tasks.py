import asyncio
import json
import logging
import uuid
from collections.abc import Callable

import dramatiq
import httpx
from redis.asyncio import Redis
from dramatiq.brokers.stub import StubBroker

from .. import (
    config,
    schemas,
    # operations,
)
from ..authentik import get_user_by_uuid
from ..constants import ProcessingStatus

# from ..events import get_event_emitter
from . import decorators

logger = logging.getLogger(__name__)

# this _stub_broker is only meant as a way to be able to register actors
# without triggering the unwanted side-effect of having dramatiq eagerly
# trying to connect to it
_stub_broker = StubBroker()
dramatiq.set_broker(_stub_broker)


@dramatiq.actor
@decorators.sld_settings
def process_data(message: str, *, settings: config.SeisLabDataSettings):
    logger.debug(
        f"Received message: {message} - Also settings.debug is {settings.debug}"
    )
    print(f"Received message: {message} - Also settings.debug is {settings.debug}")


@dramatiq.actor
@decorators.sld_settings
@decorators.redis_client
@decorators.session_maker
async def create_project(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator_id: str,
    *,
    settings: config.SeisLabDataSettings,
    redis_client: Redis,
    session_maker: Callable,
):
    logger.debug("Hi from the create_project task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    topic_name = f"progress:{request_id}"
    to_create = schemas.ProjectCreate(**json.loads(raw_to_create))
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
                message="Retrieving initiator user from authentik...",
            ).model_dump_json(),
        )
        async with httpx.AsyncClient() as client:
            initiator = await get_user_by_uuid(
                admin_token=settings.auth_admin_token,
                user_id=schemas.UserId(raw_initiator_id),
                web_client=client,
                authentik_base_url=settings.auth_internal_base_url,
            )
            logger.info(f"{initiator=}")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id,
                status=ProcessingStatus.RUNNING,
                message="Creating project...",
            ).model_dump_json(),
        )
        # async with session_maker() as session:
        #     project = await operations.create_project(
        #         to_create=to_create,
        #         initiator=initiator,
        #         session=session,
        #         settings=settings,
        #         event_emitter=get_event_emitter(settings),
        #     )

        # simulating some work
        for i in range(10):
            await asyncio.sleep(1)
            await redis_client.publish(
                topic_name,
                schemas.ProcessingMessage(
                    request_id=request_id,
                    status=ProcessingStatus.RUNNING,
                    message=f"Project is being created {i}...",
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
    except Exception as e:
        logger.error(f"Task failed with error: {e}")
        await redis_client.publish(
            topic_name,
            schemas.ProcessingMessage(
                request_id=request_id, status=ProcessingStatus.FAILED, message=str(e)
            ).model_dump_json(),
        )
