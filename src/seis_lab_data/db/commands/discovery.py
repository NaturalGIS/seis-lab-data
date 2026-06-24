import logging
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...schemas import (
    identifiers,
    discovery as discovery_schemas,
)
from .. import models
from ..queries import discovery as discovery_queries

logger = logging.getLogger(__name__)


async def create_asset_discovery_configuration(
    session: AsyncSession,
    to_create: discovery_schemas.AssetDiscoveryConfigurationCreate,
) -> models.AssetDiscoveryConfiguration:
    asset_discovery_conf = models.AssetDiscoveryConfiguration.model_validate(
        to_create.model_dump(
            exclude_none=True,
        ),
        from_attributes=False,
    )
    session.add(asset_discovery_conf)
    try:
        await session.commit()
    except IntegrityError as err:
        await session.rollback()
        raise errors.SeisLabDataError(str(err)) from err
    await session.refresh(asset_discovery_conf)
    return cast(
        models.AssetDiscoveryConfiguration,
        await discovery_queries.get_asset_discovery_configuration(
            session, to_create.id
        ),
    )


async def delete_asset_discovery_configuration(
    session: AsyncSession,
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId,
) -> None:
    if asset_discovery_conf := (
        await discovery_queries.get_asset_discovery_configuration(
            session, asset_discovery_configuration_id
        )
    ):
        await session.delete(asset_discovery_conf)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"asset_discovery_configuration with id {asset_discovery_configuration_id} does not exist."
        )


async def update_asset_discovery_configuration(
    session: AsyncSession,
    asset_discovery_configuration: models.AssetDiscoveryConfiguration,
    to_update: discovery_schemas.AssetDiscoveryConfigurationUpdate,
) -> models.AssetDiscoveryConfiguration:
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(asset_discovery_configuration, key, value)
    session.add(asset_discovery_configuration)
    await session.commit()
    await session.refresh(asset_discovery_configuration)
    return cast(
        models.AssetDiscoveryConfiguration,
        await discovery_queries.get_asset_discovery_configuration(
            session, identifiers.AssetDiscoveryConfId(asset_discovery_configuration.id)
        ),
    )
