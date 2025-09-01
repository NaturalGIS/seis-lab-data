import uuid

import pydantic

from ..constants import ProjectStatus
from .common import (
    LinkSchema,
    AtLeastEnglishLocalizableString,
    AtLeastEnglishDescription,
)


class ProjectCreate(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: AtLeastEnglishLocalizableString
    description: AtLeastEnglishDescription
    root_path: str
    links: list[LinkSchema] = []


class ProjectUpdate(pydantic.BaseModel):
    owner: str | None = None
    name: AtLeastEnglishLocalizableString | None = None
    description: AtLeastEnglishDescription
    root_path: str | None = None
    links: list[LinkSchema] | None = None


class ProjectReadListItem(pydantic.BaseModel):
    id: uuid.UUID
    slug: str
    name: AtLeastEnglishLocalizableString
    description: AtLeastEnglishDescription
    status: ProjectStatus
    is_valid: bool


class ProjectReadDetail(ProjectReadListItem):
    owner: str
    root_path: str
    links: list[LinkSchema] = []
