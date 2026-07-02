import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    constants,
    dispatch,
    errors,
)
from ..permissions import surveyrelatedrecords as record_permissions
from ..db import models
from ..db.commands import datasetcategories as category_commands
from ..db.queries import datasetcategories as category_queries
from ..schemas import (
    datasetcategories as category_schemas,
    events as event_schemas,
    identifiers,
    user as user_schemas,
)

logger = logging.getLogger(__name__)


async def create_dataset_category(
    *,
    request_id: identifiers.RequestId,
    to_create: category_schemas.DatasetCategoryCreate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.DatasetCategory:
    if not record_permissions.can_create_dataset_category(initiator):
        raise errors.SeisLabDataError(
            "User is not allowed to create a dataset category."
        )
    dataset_category = await category_commands.create_dataset_category(
        session, to_create
    )
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            resource_type=constants.ResourceType.CATEGORY,
            resource_id=str(dataset_category.id),
            request_id=request_id,
            modification=constants.ResourceModification.CREATED,
            succeeded=True,
            initiator=initiator.id,
        )
    )
    return dataset_category


async def delete_dataset_category(
    *,
    request_id: identifiers.RequestId,
    dataset_category_id: identifiers.DatasetCategoryId,
    initiator: user_schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    if not record_permissions.can_delete_dataset_category(initiator):
        raise errors.SeisLabDataError(
            "User is not allowed to delete dataset categories."
        )
    dataset_category = await category_queries.get_dataset_category(
        session, dataset_category_id
    )
    if dataset_category is None:
        raise errors.SeisLabDataError(
            f"Dataset category with id {dataset_category_id} does not exist."
        )
    await category_commands.delete_dataset_category(session, dataset_category_id)
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            resource_type=constants.ResourceType.CATEGORY,
            resource_id=str(dataset_category_id),
            request_id=request_id,
            modification=constants.ResourceModification.DELETED,
            succeeded=True,
            initiator=initiator.id,
        )
    )
