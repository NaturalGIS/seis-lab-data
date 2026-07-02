import logging
from typing import cast

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...schemas import (
    workflowstages as stage_schemas,
    identifiers,
)
from .. import models
from ..queries import workflowstages as stage_queries

logger = logging.getLogger(__name__)


async def create_workflow_stage(
    session: AsyncSession,
    to_create: stage_schemas.WorkflowStageCreate,
) -> models.WorkflowStage:
    resource = models.WorkflowStage.model_validate(to_create)
    session.add(resource)
    await session.commit()
    return cast(
        models.WorkflowStage,
        await stage_queries.get_workflow_stage(session, to_create.id),
    )


async def delete_workflow_stage(
    session: AsyncSession,
    resource_id: identifiers.WorkflowStageId,
) -> None:
    if resource := (await stage_queries.get_workflow_stage(session, resource_id)):
        await session.delete(resource)
        await session.commit()
    else:
        raise errors.SeisLabDataError(f"Workflow stage {resource_id!r} does not exist.")


async def update_workflow_stage(
    session: AsyncSession,
    resource: models.DatasetCategory,
    to_update: stage_schemas.WorkflowStageUpdate,
) -> models.WorkflowStage:
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(resource, key, value)
    session.add(resource)
    await session.commit()
    await session.refresh(resource)
    return cast(
        models.WorkflowStage,
        await stage_queries.get_workflow_stage(
            session, identifiers.WorkflowStageId(resource.id)
        ),
    )
