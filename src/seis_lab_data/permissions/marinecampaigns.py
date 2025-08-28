import logging
from .. import config

from ..schemas import MarineCampaignCreate

logger = logging.getLogger(__name__)


def can_create_marine_campaign(
    user_id: str,
    group: str,
    to_create: MarineCampaignCreate,
    *,
    settings: config.SeisLabDataSettings,
):
    return True
