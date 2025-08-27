import logging
from .. import config

logger = logging.getLogger(__name__)


def can_create_marine_campaign(
    user_id: str, group: str, *, settings: config.SeisLabDataSettings
):
    return True
