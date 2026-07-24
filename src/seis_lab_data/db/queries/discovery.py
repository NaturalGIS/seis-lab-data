import logging

from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ...schemas import identifiers
from .. import models

from .common import _get_total_num_records

logger = logging.getLogger(__name__)


_SELECT_IN_LOAD_OPTIONS = (
    selectinload(models.AssetDiscoveryConfiguration.dataset_category),
    selectinload(models.AssetDiscoveryConfiguration.workflow_stage),
)


async def get_asset_discovery_configuration(
    session: AsyncSession,
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId,
) -> models.AssetDiscoveryConfiguration | None:
    statement = (
        select(models.AssetDiscoveryConfiguration)
        .where(
            models.AssetDiscoveryConfiguration.id == asset_discovery_configuration_id
        )
        .options(*_SELECT_IN_LOAD_OPTIONS)
    )
    return (await session.exec(statement)).first()


async def get_asset_discovery_configuration_by_name(
    session: AsyncSession,
    name: str,
) -> models.AssetDiscoveryConfiguration | None:
    statement = (
        select(models.AssetDiscoveryConfiguration)
        .where(models.AssetDiscoveryConfiguration.name == name)
        .options(*_SELECT_IN_LOAD_OPTIONS)
    )
    return (await session.exec(statement)).first()


async def list_asset_discovery_configurations(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    name_filter: str | None = None,
    relative_path_regexp_filter: str | None = None,
) -> tuple[list[models.AssetDiscoveryConfiguration], int | None]:
    limit = page_size
    offset = page_size * (page - 1)
    statement = (
        select(models.AssetDiscoveryConfiguration)
        .options(*_SELECT_IN_LOAD_OPTIONS)
        .order_by(models.AssetDiscoveryConfiguration.name.asc())
    )
    if name_filter is not None:
        statement = statement.where(
            models.AssetDiscoveryConfiguration.name.ilike(f"%{name_filter}%")
        )
    if relative_path_regexp_filter is not None:
        statement = statement.where(
            models.AssetDiscoveryConfiguration.relative_path_regexp.ilike(
                f"%{relative_path_regexp_filter}%"
            )
        )
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_asset_discovery_configurations(
    session: AsyncSession,
    name_filter: str | None = None,
    relative_path_regext_filter: str | None = None,
) -> list[models.AssetDiscoveryConfiguration]:
    statement = (
        select(models.AssetDiscoveryConfiguration)
        .options(*_SELECT_IN_LOAD_OPTIONS)
        .order_by(models.AssetDiscoveryConfiguration.name.asc())
    )
    if name_filter is not None:
        statement = statement.where(
            models.AssetDiscoveryConfiguration.name.ilike(f"%{name_filter}%")
        )
    if relative_path_regext_filter is not None:
        statement = statement.where(
            models.AssetDiscoveryConfiguration.relative_path_regexp.ilike(
                f"%{relative_path_regext_filter}%"
            )
        )
    return (await session.exec(statement)).all()
