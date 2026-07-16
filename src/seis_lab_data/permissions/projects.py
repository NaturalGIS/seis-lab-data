import logging

from ..schemas.user import User
from ..constants import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_SYSTEM_ADMIN,
    ProjectStatus,
)
from ..db import models

logger = logging.getLogger(__name__)


def can_read_project(
    user: User | None,
    project: models.Project,
) -> bool:
    if user and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if project.status == ProjectStatus.PUBLISHED:
        return True
    return user is not None and project.owner_id == user.id


def can_create_project(
    user: User | None,
) -> bool:
    if user is None:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN, ROLE_EDITOR}.isdisjoint(user.roles):
        return True
    else:
        return False


def can_update_project(
    user: User | None,
    project: models.Project,
) -> bool:
    if not user:
        return False
    if not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles):
        return True
    if ROLE_EDITOR in user.roles and project.owner_id == user.id:
        return True
    return False


def can_delete_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)


def can_validate_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)


def can_change_project_status(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)


def can_discover_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_update_project(user, project)
