import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
)
from ..db import (
    commands,
    queries,
    models,
)
from .. import (
    permissions,
    schemas,
)

logger = logging.getLogger(__name__)


async def create_marine_campaign(
    to_create: schemas.MarineCampaignCreate,
    initiator: str,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
):
    # - check permissions
    # - create marine campaign
    # - generate campaign created event
    if not permissions.can_create_marine_campaign(
        initiator, "fake", to_create, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a marine campaign."
        )
    campaign = await commands.create_marine_campaign(session, to_create)
    return campaign


async def list_marine_campaigns(
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    initiator: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.MarineCampaign], int | None]:
    return await queries.list_marine_campaigns(
        session, initiator, limit, offset, include_total
    )
