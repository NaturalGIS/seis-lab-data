import logging

import dramatiq
from dramatiq.brokers.stub import StubBroker

from .. import (
    config,
    operations,
    schemas,
)
from ..db.engine import (
    get_engine,
    get_session_maker,
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
async def create_marine_campaign(to_create: dict):
    parsed_to_create = schemas.ProjectCreate(**to_create)
    settings = config.get_settings()
    engine = get_engine(settings)
    session_maker = get_session_maker(engine)
    async with session_maker() as session:
        await operations.create_project(parsed_to_create, session, settings)
