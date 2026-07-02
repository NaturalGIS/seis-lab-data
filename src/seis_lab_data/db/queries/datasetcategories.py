import logging
import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ...db import models
from .common import _get_total_num_records

logger = logging.getLogger(__name__)


async def list_dataset_categories(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    order_by_clause=models.DatasetCategory.name["en"].astext,
) -> tuple[list[models.DatasetCategory], int | None]:
    # NOTE: limit, offset and order_by are applied only when asking the
    # session to exec because we want to reuse the statement later, to count
    # total number of records
    statement = select(models.DatasetCategory)
    items = (
        await session.exec(
            statement.limit(limit).offset(offset).order_by(order_by_clause)
        )
    ).all()

    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_dataset_categories(
    session: AsyncSession, order_by_clause=models.DatasetCategory.name["en"].astext
) -> list[models.DatasetCategory]:
    _, num_total = await list_dataset_categories(session, limit=1, include_total=True)
    items, _ = await list_dataset_categories(
        session, limit=num_total, include_total=False, order_by_clause=order_by_clause
    )
    return items


async def get_dataset_category(
    session: AsyncSession,
    dataset_category_id: uuid.UUID,
) -> models.DatasetCategory | None:
    return await session.get(models.DatasetCategory, dataset_category_id)


async def get_dataset_category_by_english_name(
    session: AsyncSession, name: str
) -> models.DatasetCategory | None:
    statement = select(models.DatasetCategory).where(
        models.DatasetCategory.name["en"].astext == name
    )
    return (await session.exec(statement)).first()
