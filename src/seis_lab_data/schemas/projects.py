import pydantic

from ..constants import ProjectStatus
from .common import (
    AtLeastEnglishName,
    AtLeastEnglishDescription,
    LinkSchema,
    ProjectId,
    UserId,
)


class ProjectCreate(pydantic.BaseModel):
    id: ProjectId
    owner: UserId
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    root_path: str
    links: list[LinkSchema] = []


class ProjectUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    name: AtLeastEnglishName | None = None
    description: AtLeastEnglishDescription | None = None
    root_path: str | None = None
    links: list[LinkSchema] | None = None


class ProjectReadListItem(pydantic.BaseModel):
    id: ProjectId
    slug: str
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    status: ProjectStatus
    is_valid: bool


class ProjectReadDetail(ProjectReadListItem):
    owner: UserId
    root_path: str
    links: list[LinkSchema] = []
