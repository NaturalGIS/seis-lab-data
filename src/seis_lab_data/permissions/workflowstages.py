import logging

from ..schemas.user import User

from .common import can_manage_item

logger = logging.getLogger(__name__)


def can_create_workflow_stage(
    user: User,
) -> bool:
    return can_manage_item(user)


def can_delete_workflow_stage(
    user: User,
) -> bool:
    return can_create_workflow_stage(user)


def can_update_workflow_stage(
    user: User,
) -> bool:
    return can_create_workflow_stage(user)
