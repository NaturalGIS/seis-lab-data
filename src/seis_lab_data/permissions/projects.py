import logging

from .. import schemas
from ..constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SYSTEM_ADMIN,
    ProjectStatus,
)
from ..db import models

logger = logging.getLogger(__name__)


def can_read_project(
    user: schemas.User | None,
    project: models.Project,
) -> bool:
    if user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if project.status == ProjectStatus.PUBLISHED:
        return True
    return user and project.owner == user.id


def can_create_project(
    user: schemas.User | None,
) -> bool:
    if user is None:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN, ROLE_EDITOR}.isdisjoint(user.roles):
        return True
    else:
        return False


def can_update_project(
    user: schemas.User | None,
    project: models.Project,
) -> bool:
    if not user:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if ROLE_EDITOR in user.roles and project.owner == user.id:
        return True
    return False


def can_delete_project(
    user: schemas.User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)


def can_validate_project(
    user: schemas.User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)


def can_change_project_status(
    user: schemas.User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)
