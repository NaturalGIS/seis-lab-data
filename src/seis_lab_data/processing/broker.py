import logging

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from .. import config

# This import is needed - DO NOT REMOVE
# Dramatiq's @actor decorator tries to eagerly connect to the global dramatiq broker
# and this does not play well with using a factory pattern to create the worker,
# as it means the worker is not available at import time yet.
# The following import is part of a workaround that uses the dramatiq StubBroker
# as the initial broker where actors are registered and then changes to a real
# broker by calling the `setup_broker()` function, as defined in this module.
# This import of the tasks module causes existing actors to be discovered and
# registered with dramatiq (using the stub broker). When calling the `dramatiq` cli,
# we rely on this import being done before the call to our own `setup_broker()` function,
# as we need to ensure the actors are known before we set the real broker.
from ..processing import tasks  # noqa

logger = logging.getLogger(__name__)


def setup_broker(settings: config.SeisLabDataSettings | None = None) -> None:
    """Setup the dramatiq message broker.

    This function relies on all actors having already been imported and registered into
    a global dramatiq stub broker. It works by inspecting this previous broker, gathering
    existing actors from it and then re-registering them with the real broker, which it
    also creates and sets as the global broker for dramatiq.

    This is part of a workaround that enables using dramatiq together with a factory
    pattern. It is not very pretty, but it works.
    """
    settings = settings or config.get_settings()
    if settings.message_broker_dsn is not None:
        new_broker = RedisBroker(
            host=settings.message_broker_dsn.host,
            port=settings.message_broker_dsn.port,
        )
        old_broker = dramatiq.get_broker()
        # reconfigure actors to use the new broker
        for existing_actor_name in old_broker.get_declared_actors():
            actor = old_broker.get_actor(existing_actor_name)
            actor.broker = new_broker
            new_broker.declare_actor(actor)
        dramatiq.set_broker(new_broker)
    else:
        logger.debug("No message broker DSN configured, skipping broker setup")
