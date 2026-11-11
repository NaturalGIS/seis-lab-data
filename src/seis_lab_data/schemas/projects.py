import datetime as dt
from typing import Annotated

import pydantic

from ..constants import ProjectStatus
from ..db import models
from .common import (
    LinkSchema,
    DraftDescription,
    DraftName,
    PolygonOut,
    PossiblyInvalidPolygon,
    serialize_id,
    serialize_possibly_empty_date,
)
from .identifiers import ProjectId


class ProjectCreate(pydantic.BaseModel):
    id: ProjectId
    name: DraftName
    description: DraftDescription = ""
    links: list[LinkSchema] = []
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None


class ProjectUpdate(pydantic.BaseModel):
    name: DraftName | None = None
    description: DraftDescription | None = None
    links: list[LinkSchema] | None = None
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None


class ProjectReadEmbedded(pydantic.BaseModel):
    id: Annotated[ProjectId, pydantic.PlainSerializer(serialize_id)]
    name: DraftName
    status: ProjectStatus
    validation_result: models.ValidationResult | None
    bbox_4326: PolygonOut | None
    temporal_extent_begin: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    temporal_extent_end: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadEmbedded":
        return cls(**instance.model_dump())


class ProjectReadListItem(ProjectReadEmbedded):
    description: DraftDescription
    has_thumbnail: bool

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadListItem":
        return cls(
            **instance.model_dump(), has_thumbnail=instance.thumbnail is not None
        )


class ProjectReadDetail(ProjectReadListItem):
    links: list[LinkSchema] = []
    bbox_4326: PolygonOut | None

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadDetail":
        return cls(
            **instance.model_dump(), has_thumbnail=instance.thumbnail is not None
        )


class AssetDiscoveryConfigurationReadListItem(pydantic.BaseModel): ...
