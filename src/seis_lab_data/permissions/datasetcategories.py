import logging

from ..schemas.user import User

from .common import can_manage_item

logger = logging.getLogger(__name__)


def can_create_dataset_category(
    user: User,
) -> bool:
    return can_manage_item(user)


def can_delete_dataset_category(
    user: User,
) -> bool:
    return can_create_dataset_category(user)


def can_update_dataset_category(
    user: User,
) -> bool:
    return can_create_dataset_category(user)
