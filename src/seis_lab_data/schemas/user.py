import dataclasses

from .common import UserId


@dataclasses.dataclass
class User:
    id: UserId
    email: str
    username: str
    roles: list[str]
    active: bool = False
