import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    constants,
    dispatch,
    errors,
)
from ..permissions import workflowstages as stage_permissions
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
) -> models.WorkflowStage | None:
    try:
        if not stage_permissions.can_create_workflow_stage(initiator):
            raise errors.SeisLabDataError(
                "User is not allowed to create a workflow stage."
            )
        resource = await stage_commands.create_workflow_stage(session, to_create)
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.WORKFLOW_STAGE,
                resource_id=None,
                modification=constants.ResourceModification.CREATED,
                succeeded=False,
                details=str(err),
            )
        )
        return None
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.WORKFLOW_STAGE,
            resource_id=str(resource.id),
            modification=constants.ResourceModification.CREATED,
            succeeded=True,
        )
    )
    return resource


async def update_workflow_stage(
    *,
    request_id: identifiers.RequestId,
    resource_id: identifiers.WorkflowStageId,
    to_update: stage_schemas.WorkflowStageUpdate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.WorkflowStage | None:
    try:
        if (
            resource := await stage_queries.get_workflow_stage(session, resource_id)
        ) is None:
            raise errors.SeisLabDataError(
                f"Workflow stage {resource_id!r} does not exist."
            )
        if not stage_permissions.can_update_workflow_stage(initiator):
            raise errors.SeisLabDataError("User not allowed to update workflow stage.")
        updated_resource = await stage_commands.update_workflow_stage(
            session, resource, to_update
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.WORKFLOW_STAGE,
                resource_id=str(resource_id),
                modification=constants.ResourceModification.UPDATED,
                succeeded=False,
                details=str(err),
            )
        )
        return None

    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.WORKFLOW_STAGE,
            resource_id=str(resource_id),
            modification=constants.ResourceModification.UPDATED,
            succeeded=True,
        )
    )
    return updated_resource


async def delete_workflow_stage(
    *,
    request_id: identifiers.RequestId,
    resource_id: identifiers.WorkflowStageId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    try:
        if (await stage_queries.get_workflow_stage(session, resource_id)) is None:
            raise errors.SeisLabDataError(
                f"Workflow stage {resource_id!r} does not exist."
            )
        if not stage_permissions.can_delete_workflow_stage(initiator):
            raise errors.SeisLabDataError("User not allowed to delete workflow stages.")
        await stage_commands.delete_workflow_stage(session, resource_id)
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.WORKFLOW_STAGE,
                resource_id=str(resource_id),
                modification=constants.ResourceModification.DELETED,
                succeeded=False,
                details=str(err),
            )
        )
        return None
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.WORKFLOW_STAGE,
            resource_id=str(resource_id),
            modification=constants.ResourceModification.DELETED,
            succeeded=True,
        )
    )
