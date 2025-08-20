import logging

import dramatiq
from dramatiq.brokers.stub import StubBroker

from .. import config

logger = logging.getLogger(__name__)

# this _stub_broker is only meant as a way to be able to register actors
# without triggering the unwanted side-effect of having dramatiq eagerly
# trying to connect to it
_stub_broker = StubBroker()
dramatiq.set_broker(_stub_broker)
print("dramatiq broker set to the stub broker")


@dramatiq.actor
def process_data(message: str):
    settings = config.get_settings()
    logger.debug(
        f"Received message: {message} - Also settings.debug is {settings.debug}"
    )
    print(f"Received message: {message} - Also settings.debug is {settings.debug}")
