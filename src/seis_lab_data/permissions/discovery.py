import logging

from ..db import models
from ..constants import (
    ROLE_ADMIN,
    ROLE_SYSTEM_ADMIN,
)
from ..schemas.user import User

from .projects import can_update_project

logger = logging.getLogger(__name__)


def can_create_asset_discovery_configuration(user: User) -> bool:
    return not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(user.roles)


def can_update_asset_discovery_configuration(user: User) -> bool:
    return can_create_asset_discovery_configuration(user)


def can_delete_asset_discovery_configuration(user: User) -> bool:
    return can_create_asset_discovery_configuration(user)


def can_discover_project_survey_missions(user: User, project: models.Project) -> bool:
    return can_update_project(user, project)
