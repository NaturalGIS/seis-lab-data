import logging

from .. import (
    config,
    schemas,
)
from ..constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ProjectStatus,
)
from ..db import models

logger = logging.getLogger(__name__)


def can_read_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user and ROLE_ADMIN in user.roles:
        return True
    if project.status == ProjectStatus.PUBLISHED:
        return True
    return user and project.owner == user.id


def can_create_project(
    user: schemas.User | None,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    elif not {ROLE_ADMIN, ROLE_EDITOR}.isdisjoint(set(user.roles)):
        return True
    else:
        return False


def can_update_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    if user is None:
        return False
    return ROLE_ADMIN in user.roles or project.owner == user.id


def can_delete_project(
    user: schemas.User | None,
    project: models.Project,
    settings: config.SeisLabDataSettings,
) -> bool:
    return can_update_project(user, project, settings)


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
