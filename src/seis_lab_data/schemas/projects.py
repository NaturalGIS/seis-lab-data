import datetime as dt
import hashlib
from typing import Annotated

import pydantic

from ..constants import ProjectStatus
from ..db import models
from .common import (
    DraftDescription,
    DraftName,
    LinkSchema,
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
    # changes with the image, so that its URL does too, as the URL of a record's
    # preview does with its asset id
    thumbnail_version: str | None

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadListItem":
        return cls(
            **instance.model_dump(),
            thumbnail_version=(
                hashlib.sha256(instance.thumbnail).hexdigest()[:16]
                if instance.thumbnail is not None
                else None
            ),
        )


class ProjectReadDetail(ProjectReadListItem):
    links: list[LinkSchema] = []
    bbox_4326: PolygonOut | None

    @classmethod
    def from_db_instance(cls, instance: models.Project) -> "ProjectReadDetail":
        return cls(
            **instance.model_dump(),
            thumbnail_version=(
                hashlib.sha256(instance.thumbnail).hexdigest()[:16]
                if instance.thumbnail is not None
                else None
            ),
        )


class AssetDiscoveryConfigurationReadListItem(pydantic.BaseModel): ...
