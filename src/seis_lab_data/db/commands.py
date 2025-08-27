from sqlmodel.ext.asyncio.session import AsyncSession

from ..schemas import marinecampaigns
from . import models


async def create_marine_campaign(
    session: AsyncSession, to_create: marinecampaigns.MarineCampaignCreate
) -> models.MarineCampaign:
    campaign = models.MarineCampaign(**to_create.model_dump())
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign
