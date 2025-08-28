import uuid
import logging
from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


async def can_create_marine_campaign(
    user_id: str,
    group: str,
    to_create: schemas.MarineCampaignCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_marine_campaign(
    user_id: str,
    group: str,
    marine_campaign_id: uuid.UUID,
    *,
    settings: config.SeisLabDataSettings,
):
    return True
