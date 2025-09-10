import logging
from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


async def can_read_project(
    user: schemas.UserId,
    project_slug: str,
    *,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_create_project(
    user: schemas.User,
    settings: config.SeisLabDataSettings,
):
    return True


async def can_delete_project(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
):
    return True
