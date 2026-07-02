import json
import logging
import uuid

import dramatiq

from .. import config
from ..operations import workflowstages as stage_ops
from ..schemas import (
    workflowstages as stage_schemas,
    identifiers,
    user as user_schemas,
)

from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)

logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def create_workflow_stage(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await stage_ops.create_workflow_stage(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_create=stage_schemas.WorkflowStageCreate.model_validate_json(
                raw_to_create
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def update_workflow_stage(
    raw_request_id: str,
    raw_resource_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await stage_ops.update_workflow_stage(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            resource_id=identifiers.WorkflowStageId(uuid.UUID(raw_resource_id)),
            to_update=stage_schemas.WorkflowStageUpdate.model_validate_json(
                raw_to_update
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def delete_workflow_stage(
    raw_request_id: str,
    raw_resource_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await stage_ops.delete_workflow_stage(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            resource_id=identifiers.WorkflowStageId(uuid.UUID(raw_resource_id)),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
