from typing import TYPE_CHECKING
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ...db import models
from .common import _get_total_num_records

if TYPE_CHECKING:
    from ... import schemas


async def list_projects(
    session: AsyncSession,
    user: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.Project], int | None]:
    statement = select(models.Project)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_projects(
    session: AsyncSession,
) -> list[models.Project]:
    _, num_total = await list_projects(session, limit=1, include_total=True)
    items, _ = await list_projects(session, limit=num_total, include_total=False)
    return items


async def get_project(
    session: AsyncSession,
    project_id: "schemas.ProjectId",
) -> models.Project | None:
    return await session.get(models.Project, project_id)


async def get_project_by_english_name(
    session: AsyncSession,
    english_name: str,
) -> models.Project | None:
    statement = select(models.Project).where(
        models.Project.name["en"].astext == english_name
    )
    return (await session.exec(statement)).first()
