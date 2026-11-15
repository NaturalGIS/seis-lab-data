import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    constants,
    dispatch,
    errors,
)
from ..db import models
from ..db.commands import datasetcategories as category_commands
from ..db.queries import datasetcategories as category_queries
from ..permissions import datasetcategories as category_permissions
from ..schemas import datasetcategories as category_schemas
from ..schemas import events as event_schemas
from ..schemas import identifiers
from ..schemas import user as user_schemas

logger = logging.getLogger(__name__)


async def create_dataset_category(
    *,
    request_id: identifiers.RequestId,
    to_create: category_schemas.DatasetCategoryCreate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.DatasetCategory | None:
    try:
        if not category_permissions.can_create_dataset_category(initiator):
            raise errors.SeisLabDataError(
                errors.N_("User is not allowed to create dataset categories.")
            )
        resource = await category_commands.create_dataset_category(session, to_create)
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.CATEGORY,
                resource_id=None,
                resource_name=to_create.name,
                modification=constants.ResourceModification.CREATED,
                succeeded=False,
                details=err.message,
                details_params=err.params,
            )
        )
        return None

    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.CATEGORY,
            resource_id=str(resource.id),
            resource_name=resource.name,
            modification=constants.ResourceModification.CREATED,
            succeeded=True,
        )
    )
    return resource


async def update_dataset_category(
    *,
    request_id: identifiers.RequestId,
    resource_id: identifiers.DatasetCategoryId,
    to_update: category_schemas.DatasetCategoryUpdate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.DatasetCategory | None:
    resource_name = None
    try:
        if (
            resource := await category_queries.get_dataset_category(
                session, resource_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                errors.N_("Dataset category %(id)s does not exist."),
                id=str(resource_id),
            )
        resource_name = resource.name
        if not category_permissions.can_update_dataset_category(initiator):
            raise errors.SeisLabDataError(
                errors.N_("User is not allowed to update dataset categories.")
            )
        updated_resource = await category_commands.update_dataset_category(
            session, resource, to_update
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.CATEGORY,
                resource_id=str(resource_id),
                resource_name=resource_name,
                modification=constants.ResourceModification.UPDATED,
                succeeded=False,
                details=err.message,
                details_params=err.params,
            )
        )
        return None

    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.CATEGORY,
            resource_id=str(resource_id),
            resource_name=updated_resource.name,
            modification=constants.ResourceModification.UPDATED,
            succeeded=True,
        )
    )
    return updated_resource


async def delete_dataset_category(
    *,
    request_id: identifiers.RequestId,
    resource_id: identifiers.DatasetCategoryId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    resource_name = None
    try:
        if (
            resource := await category_queries.get_dataset_category(
                session, resource_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                errors.N_("Dataset category %(id)s does not exist."),
                id=str(resource_id),
            )
        resource_name = resource.name
        if not category_permissions.can_delete_dataset_category(initiator):
            raise errors.SeisLabDataError(
                errors.N_("User is not allowed to delete dataset categories.")
            )
        await category_commands.delete_dataset_category(session, resource_id)
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                resource_type=constants.ResourceType.CATEGORY,
                resource_id=str(resource_id),
                resource_name=resource_name,
                request_id=request_id,
                modification=constants.ResourceModification.DELETED,
                succeeded=False,
                initiator=initiator.id,
                details=err.message,
                details_params=err.params,
            )
        )
        return
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            resource_type=constants.ResourceType.CATEGORY,
            resource_id=str(resource_id),
            resource_name=resource_name,
            request_id=request_id,
            modification=constants.ResourceModification.DELETED,
            succeeded=True,
            initiator=initiator.id,
        )
    )
