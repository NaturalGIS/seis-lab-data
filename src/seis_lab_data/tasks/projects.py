import json
import logging
import uuid

import dramatiq

from .. import config
from ..operations import projects as project_ops
from ..schemas import (
    identifiers,
    projects as project_schemas,
    user as user_schemas,
)
from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)
logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def create_project(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await project_ops.create_project(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_create=project_schemas.ProjectCreate.model_validate_json(raw_to_create),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def update_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await project_ops.update_project(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            project_id=identifiers.ProjectId(uuid.UUID(raw_project_id)),
            to_update=project_schemas.ProjectUpdate.model_validate_json(raw_to_update),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def delete_project(
    raw_request_id: str,
    raw_project_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await project_ops.delete_project(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            project_id=identifiers.ProjectId(uuid.UUID(raw_project_id)),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
