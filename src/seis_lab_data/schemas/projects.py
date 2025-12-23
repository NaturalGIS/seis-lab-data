import datetime as dt
from typing import Annotated

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
    serialize_id,
    serialize_possibly_empty_date,
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
    id: Annotated[ProjectId, pydantic.PlainSerializer(serialize_id)]
    name: LocalizableDraftName
    status: ProjectStatus
    validation_result: models.ValidationResult | None
    root_path: str
    bbox_4326: PolygonOut | None
    temporal_extent_begin: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    temporal_extent_end: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    num_survey_missions: int
    num_survey_related_records: int

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
    links: list[LinkSchema] = []
    bbox_4326: PolygonOut | None

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadDetail":
        return cls(**instance.model_dump())
