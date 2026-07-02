import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    constants,
    dispatch,
    errors,
)
from ..permissions import surveyrelatedrecords as record_permissions
from ..db import models
from ..db.commands import workflowstages as stage_commands
from ..db.queries import workflowstages as stage_queries
from ..schemas import (
    events as event_schemas,
    identifiers,
    user as user_schemas,
    workflowstages as stage_schemas,
)

logger = logging.getLogger(__name__)


async def create_workflow_stage(
    *,
    request_id: identifiers.RequestId,
    to_create: stage_schemas.WorkflowStageCreate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.WorkflowStage:
    if not record_permissions.can_create_workflow_stage(initiator):
        raise errors.SeisLabDataError("User is not allowed to create a workflow stage.")
    workflow_stage = await stage_commands.create_workflow_stage(session, to_create)
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            resource_type=constants.ResourceType.WORKFLOW_STAGE,
            resource_id=str(workflow_stage.id),
            request_id=request_id,
            modification=constants.ResourceModification.CREATED,
            succeeded=True,
            initiator=initiator.id,
        )
    )
    return workflow_stage


async def delete_workflow_stage(
    *,
    request_id: identifiers.RequestId,
    workflow_stage_id: identifiers.WorkflowStageId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    if not record_permissions.can_delete_workflow_stage(initiator):
        raise errors.SeisLabDataError("User is not allowed to delete workflow stages.")
    workflow_stage = await stage_queries.get_workflow_stage(session, workflow_stage_id)
    if workflow_stage is None:
        raise errors.SeisLabDataError(
            f"Workflow stage with id {workflow_stage_id} does not exist."
        )
    await stage_commands.delete_workflow_stage(session, workflow_stage_id)
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            resource_type=constants.ResourceType.WORKFLOW_STAGE,
            resource_id=str(workflow_stage.id),
            request_id=request_id,
            modification=constants.ResourceModification.DELETED,
            succeeded=True,
            initiator=initiator.id,
        )
    )
