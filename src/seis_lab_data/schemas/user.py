import dataclasses
import typing

UserId = typing.NewType("UserId", str)


@dataclasses.dataclass(frozen=True)
class User:
    id: UserId
    email: str
    username: str
    roles: list[str]
    active: bool = False
