import logging

from ..schemas.user import User
from ..constants import (
    ROLE_ADMIN,
    ROLE_SYSTEM_ADMIN,
)

logger = logging.getLogger(__name__)


def can_create_workflow_stage(
    user: User,
) -> bool:
    return user is not None and not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(
        user.roles
    )


def can_delete_workflow_stage(
    user: User,
) -> bool:
    return can_create_workflow_stage(user)


def can_update_workflow_stage(
    user: User,
) -> bool:
    return can_create_workflow_stage(user)
