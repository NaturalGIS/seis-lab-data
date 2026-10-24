import logging

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    func,
    select,
)

from ...db import models
from ...schemas import identifiers
from .common import _get_total_num_records

logger = logging.getLogger(__name__)


async def list_dataset_categories(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    name_filter: str | None = None,
) -> tuple[list[models.DatasetCategory], int | None]:
    limit = page_size
    offset = page_size * (page - 1)
    statement = select(models.DatasetCategory).order_by(
        func.lower(models.DatasetCategory.name)
    )
    if name_filter is not None:
        statement = statement.where(
            models.DatasetCategory.name.ilike(f"%{name_filter}%")
        )
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_dataset_categories(
    session: AsyncSession,
    name_filter: str | None = None,
) -> list[models.DatasetCategory]:
    statement = select(models.DatasetCategory).order_by(
        func.lower(models.DatasetCategory.name)
    )
    if name_filter is not None:
        statement = statement.where(
            models.DatasetCategory.name.ilike(f"%{name_filter}%")
        )
    return (await session.exec(statement)).all()


async def get_dataset_category(
    session: AsyncSession,
    dataset_category_id: identifiers.DatasetCategoryId,
) -> models.DatasetCategory | None:
    return await session.get(models.DatasetCategory, dataset_category_id)


async def get_dataset_category_by_name(
    session: AsyncSession, name: str
) -> models.DatasetCategory | None:
    statement = select(models.DatasetCategory).where(
        models.DatasetCategory.name == name
    )
    return (await session.exec(statement)).first()
