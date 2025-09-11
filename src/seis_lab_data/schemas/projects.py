import pydantic
from slugify import slugify

from ..constants import ProjectStatus
from ..db import models
from .common import (
    LinkSchema,
    LocalizableDraftDescription,
    LocalizableDraftName,
    ProjectId,
    UserId,
)


class ProjectCreate(pydantic.BaseModel):
    id: ProjectId
    owner: UserId
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    root_path: str
    links: list[LinkSchema] = []

    @pydantic.computed_field
    @property
    def slug(self) -> str:
        return slugify(self.name.get("en", ""))


class ProjectUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    name: LocalizableDraftName | None = None
    description: LocalizableDraftDescription | None = None
    root_path: str | None = None
    links: list[LinkSchema] | None = None


class ProjectReadEmbedded(pydantic.BaseModel):
    id: ProjectId
    slug: str
    name: LocalizableDraftName
    status: ProjectStatus
    is_valid: bool

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadEmbedded":
        return cls(**instance.model_dump())


class ProjectReadListItem(ProjectReadEmbedded):
    description: LocalizableDraftDescription

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadEmbedded":
        return cls(**instance.model_dump())


class ProjectReadDetail(ProjectReadListItem):
    owner: UserId
    root_path: str
    links: list[LinkSchema] = []
