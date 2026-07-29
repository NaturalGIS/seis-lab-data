from ..schemas.user import User
from .. import constants


def is_editor(*user_role: str) -> bool:
    return not {
        constants.ROLE_SYSTEM_ADMIN,
        constants.ROLE_ADMIN,
        constants.ROLE_EDITOR,
    }.isdisjoint(user_role)


def can_manage_item(
    user: User | None,
) -> bool:
    if user is None:
        return False
    return is_editor(*user.roles)
