import json
import logging
import uuid

import dramatiq

from .. import (
    config,
    constants,
)
from ..schemas import (
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
async def discover_project_contents(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    project_id = identifiers.ProjectId(uuid.UUID(raw_project_id))
    initiator = user_schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        try:
            await discovery_ops.run_project_discovery(
                request_id=request_id,
                project_id=project_id,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
                settings=settings,
                user=initiator,
            )
        except Exception:
            logger.exception("Task failed")
            await session.rollback()
            await project_ops.change_project_status(
                request_id=request_id,
                project_id=project_id,
                target_status=constants.ProjectStatus.DRAFT,
                initiator=initiator,
                session=session,
                event_dispatcher=settings.get_event_dispatcher(),
            )
