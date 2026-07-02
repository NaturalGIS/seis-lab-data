import logging
import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ...db import models
from .common import _get_total_num_records

logger = logging.getLogger(__name__)


async def list_dataset_categories(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
) -> tuple[list[models.DatasetCategory], int | None]:
    limit = page_size
    offset = page_size * (page - 1)
    statement = (
        select(models.DatasetCategory)
        .order_by(models.DatasetCategory.name["en"].astext.desc())
        .offset(offset)
        .limit(limit)
    )
    if en_name_filter is not None:
        statement = statement.where(
            models.DatasetCategory.name["en"].astext.ilike(f"%{en_name_filter}%")
        )
    if pt_name_filter is not None:
        statement = statement.where(
            models.DatasetCategory.name["pt"].astext.ilike(f"%{pt_name_filter}%")
        )
    items = (await session.exec(statement)).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_dataset_categories(
    session: AsyncSession,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
) -> list[models.DatasetCategory]:
    statement = select(models.DatasetCategory).order_by(
        models.DatasetCategory.name["en"].astext.desc()
    )
    if en_name_filter is not None:
        statement = statement.where(
            models.DatasetCategory.name["en"].astext.ilike(f"%{en_name_filter}%")
        )
    if pt_name_filter is not None:
        statement = statement.where(
            models.DatasetCategory.name["pt"].astext.ilike(f"%{pt_name_filter}%")
        )
    return (await session.exec(statement)).all()


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
