import uuid
import logging
from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


async def can_read_marine_campaign(
    user: schemas.User,
    marine_campaign_slug: str,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_create_marine_campaign(
    user: schemas.User,
    to_create: schemas.ProjectCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_marine_campaign(
    user: schemas.User,
    marine_campaign_id: uuid.UUID,
    *,
    settings: config.SeisLabDataSettings,
):
    return True
