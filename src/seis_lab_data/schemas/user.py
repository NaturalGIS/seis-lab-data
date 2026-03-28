import dataclasses

from starlette.authentication import BaseUser

from .common import UserId


@dataclasses.dataclass
class User(BaseUser):
    id: UserId
    email: str
    username: str
    roles: list[str]
    name: str = ""
    active: bool = False

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return str(self.id)
