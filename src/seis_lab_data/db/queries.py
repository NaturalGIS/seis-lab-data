from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    func,
    select,
)

from . import models


async def _get_total_num_records(session: AsyncSession, statement):
    return (await session.exec(select(func.count()).select_from(statement))).first()


async def list_marine_campaigns(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.MarineCampaign], int | None]:
    statement = select(models.MarineCampaign)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_marine_campaigns(
    session: AsyncSession,
) -> list[models.MarineCampaign]:
    _, num_total = await list_marine_campaigns(session, limit=1, include_total=True)
    items, _ = await list_marine_campaigns(
        session, limit=num_total, include_total=False
    )
    return items
