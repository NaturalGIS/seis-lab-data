import logging
from typing import Protocol

from .. import schemas

logger = logging.getLogger(__name__)


class EventEmitterProtocol(Protocol):
    def __call__(self, event: schemas.SeisLabDataEvent) -> None:
        raise NotImplementedError


def no_op_emit_event(event: schemas.SeisLabDataEvent) -> None:
    """An event emitter that just logs the event."""
    logger.debug(f"no-op emit event called with {event=}")


def null_emitter(event: schemas.SeisLabDataEvent) -> None:
    """An event emitter that does nothing."""
    ...


def emit_event(event: schemas.SeisLabDataEvent) -> None: ...
