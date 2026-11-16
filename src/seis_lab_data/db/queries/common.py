from sqlmodel import (
    func,
    select,
)
from sqlmodel.ext.asyncio.session import AsyncSession


async def _get_total_num_records(session: AsyncSession, statement):
    return (
        await session.exec(select(func.count()).select_from(statement.subquery()))
    ).first()
