import logging

from ..db import models
from ..schemas.user import User

from .common import can_manage_item

logger = logging.getLogger(__name__)


def can_read_private_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return user is not None


def can_create_project(
    user: User | None,
) -> bool:
    return can_manage_item(user)


def can_update_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_manage_item(user)


def can_delete_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_manage_item(user)


def can_validate_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_manage_item(user)


def can_change_project_status(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_manage_item(user)


def can_discover_project(
    user: User | None,
    project: models.Project,
) -> bool:
    return can_manage_item(user)
