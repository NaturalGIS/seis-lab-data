import logging
from .. import (
    config,
    schemas,
)

logger = logging.getLogger(__name__)


async def can_read_project(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_create_project(
    user: schemas.User,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_delete_project(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_update_project(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return True


async def can_validate_project(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return await can_update_project(user, project_id, settings=settings)


async def can_change_project_status(
    user: schemas.User,
    project_id: schemas.ProjectId,
    *,
    settings: config.SeisLabDataSettings,
) -> bool:
    return await can_update_project(user, project_id, settings=settings)
