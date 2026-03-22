import logging

from .. import (
    config,
    schemas,
)
from ..constants import ADMIN_ROLE, ProjectStatus
from ..db import models

logger = logging.getLogger(__name__)


def _is_admin(user: schemas.User) -> bool:
    return ADMIN_ROLE in user.roles


def can_read_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is not None and _is_admin(user):
        return True
    if project.status == ProjectStatus.PUBLISHED:
        return True
    return user is not None and project.owner == user.id


def can_create_project(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    return user is not None


def can_delete_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return _is_admin(user) or project.owner == user.id


def can_update_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return _is_admin(user) or project.owner == user.id


def can_validate_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_project(user, project, settings)


def can_change_project_status(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_project(user, project, settings)
