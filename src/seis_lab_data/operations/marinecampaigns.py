import uuid
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
    events,
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
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
):
    if initiator is None or not await permissions.can_create_marine_campaign(
        initiator, to_create, settings=settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a marine campaign."
        )
    campaign = await commands.create_marine_campaign(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.MARINE_CAMPAIGN_CREATED,
            initiator=initiator,
            payload=schemas.EventPayload(
                after=schemas.MarineCampaignReadDetail(
                    **campaign.model_dump()
                ).model_dump()
            ),
        )
    )
    return campaign


async def delete_marine_campaign(
    marine_campaign_id: uuid.UUID,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_marine_campaign(
        initiator, marine_campaign_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to delete marine campaigns.")
    marine_campaign = await queries.get_marine_campaign(session, marine_campaign_id)
    if marine_campaign is None:
        raise errors.SeisLabDataError(
            f"Marine campaign with id {marine_campaign_id} does not exist."
        )
    serialized_campaign = schemas.MarineCampaignReadDetail(
        **marine_campaign.model_dump()
    ).model_dump()
    await commands.delete_marine_campaign(session, marine_campaign_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.MARINE_CAMPAIGN_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_campaign),
        )
    )


async def list_marine_campaigns(
    session: AsyncSession,
    initiator: schemas.User | None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.MarineCampaign], int | None]:
    return await queries.list_marine_campaigns(
        session, initiator, limit, offset, include_total
    )


async def get_marine_campaign_by_slug(
    marine_cammpaign_slug: str,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> models.MarineCampaign | None:
    if initiator is None or not permissions.can_read_marine_campaign(
        initiator, marine_cammpaign_slug, settings=settings
    ):
        raise errors.SeisLabDataError(
            f"User is not allowed to read marine campaign {marine_cammpaign_slug!r}."
        )
    return await queries.get_marine_campaign_by_slug(session, marine_cammpaign_slug)
