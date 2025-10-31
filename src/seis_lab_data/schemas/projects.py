import datetime as dt

import pydantic

from ..constants import ProjectStatus
from ..db import models
from .common import (
    LinkSchema,
    LocalizableDraftDescription,
    LocalizableDraftName,
    PolygonOut,
    PossiblyInvalidPolygon,
    ProjectId,
    UserId,
)


class ProjectCreate(pydantic.BaseModel):
    id: ProjectId
    owner: UserId
    name: LocalizableDraftName
    description: LocalizableDraftDescription | None = None
    root_path: str
    links: list[LinkSchema] = []
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None


class ProjectUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    name: LocalizableDraftName | None = None
    description: LocalizableDraftDescription | None = None
    root_path: str | None = None
    links: list[LinkSchema] | None = None
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None


class ProjectReadEmbedded(pydantic.BaseModel):
    id: ProjectId
    name: LocalizableDraftName
    status: ProjectStatus
    is_valid: bool
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadEmbedded":
        return cls(**instance.model_dump())


class ProjectReadListItem(ProjectReadEmbedded):
    description: LocalizableDraftDescription

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadListItem":
        return cls(**instance.model_dump())


class ProjectReadDetail(ProjectReadListItem):
    owner: UserId
    root_path: str
    links: list[LinkSchema] = []
    bbox_4326: PolygonOut | None

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadDetail":
        return cls(**instance.model_dump())
