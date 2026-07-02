import logging
from typing import cast

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...schemas import (
    datasetcategories as category_schemas,
    identifiers,
)
from .. import models
from ..queries import datasetcategories as category_queries

logger = logging.getLogger(__name__)


async def create_dataset_category(
    session: AsyncSession,
    to_create: category_schemas.DatasetCategoryCreate,
) -> models.DatasetCategory:
    resource = models.DatasetCategory(
        **to_create.model_dump(),
    )
    session.add(resource)
    await session.commit()
    return cast(
        models.DatasetCategory,
        await category_queries.get_dataset_category(session, resource.id),
    )


async def delete_dataset_category(
    session: AsyncSession,
    resource_id: identifiers.DatasetCategoryId,
) -> None:
    if resource := (await category_queries.get_dataset_category(session, resource_id)):
        await session.delete(resource)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Dataset category {resource_id!r} does not exist."
        )


async def update_dataset_category(
    session: AsyncSession,
    resource: models.DatasetCategory,
    to_update: category_schemas.DatasetCategoryUpdate,
) -> models.DatasetCategory:
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(resource, key, value)
    session.add(resource)
    await session.commit()
    await session.refresh(resource)
    return cast(
        models.DatasetCategory,
        await category_queries.get_dataset_category(
            session, identifiers.DatasetCategoryId(resource.id)
        ),
    )
