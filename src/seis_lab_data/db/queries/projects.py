import shapely
from typing import TYPE_CHECKING
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    func,
    or_,
    select,
)

from ...db import models
from .common import _get_total_num_records

if TYPE_CHECKING:
    from ... import schemas


async def paginated_list_projects(
    session: AsyncSession,
    user: str | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
) -> tuple[list[models.Project], int | None]:
    limit = page_size
    offset = limit * (page - 1)
    return await list_projects(
        session,
        user,
        limit,
        offset,
        include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
    )


# TODO: explicitly add an 'order by' clause
# TODO: only show projects that are either owned by user or published
async def list_projects(
    session: AsyncSession,
    user: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
) -> tuple[list[models.Project], int | None]:
    statement = select(models.Project)
    if en_name_filter:
        statement = statement.where(
            models.Project.name["en"].astext.ilike(f"%{en_name_filter}%")
        )
    if pt_name_filter:
        statement = statement.where(
            models.Project.name["pt"].astext.ilike(f"%{pt_name_filter}%")
        )
    if spatial_intersect is not None:
        statement = statement.where(
            or_(
                func.ST_Intersects(
                    models.Project.bbox_4326,
                    func.ST_GeomFromText(spatial_intersect.wkt, 4326),
                ),
                models.Project.bbox_4326.is_(None),
            )
        )
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
