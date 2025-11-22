import logging
from typing import Protocol

from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


class EventEmitterProtocol(Protocol):
    def __call__(self, event: schemas.SeisLabDataEvent):
        raise NotImplementedError


def get_event_emitter(settings: config.SeisLabDataSettings) -> EventEmitterProtocol:
    return emit_event if settings.emit_events else no_op_emit_event


def no_op_emit_event(event: schemas.SeisLabDataEvent):
    """An event emitter that just logs the event."""
    logger.debug(f"no-op emit event called with {event=}")


def null_emitter(event: schemas.SeisLabDataEvent):
    """An event emitter that does nothing."""
    ...


def emit_event(event: schemas.SeisLabDataEvent): ...
