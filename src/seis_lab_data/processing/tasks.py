import json
import logging
import uuid

import dramatiq
from dramatiq.brokers.stub import StubBroker

from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)

# this _stub_broker is only meant as a way to be able to register actors
# without triggering the unwanted side-effect of having dramatiq eagerly
# trying to connect to it
_stub_broker = StubBroker()
dramatiq.set_broker(_stub_broker)


@dramatiq.actor
def process_data(message: str):
    settings = config.get_settings()
    logger.debug(
        f"Received message: {message} - Also settings.debug is {settings.debug}"
    )
    print(f"Received message: {message} - Also settings.debug is {settings.debug}")


@dramatiq.actor
async def create_project(
    raw_request_id: str,
    raw_to_create: str,
):
    logger.debug("Hi from the create_project task")
    request_id = schemas.RequestId(uuid.UUID(raw_request_id))
    to_create = schemas.ProjectCreate(**json.loads(raw_to_create))
    logger.debug(f"{request_id=}")
    logger.debug(f"{to_create=}")
