import datetime as dt
import uuid

import pydantic

from ..constants import SurveyMissionStatus
from ..db import models
from .common import (
    LinkSchema,
    LocalizableDraftDescription,
    LocalizableDraftName,
    PolygonOut,
    PossiblyInvalidPolygon,
    ProjectId,
    SurveyMissionId,
    UserId,
)
from .projects import ProjectReadEmbedded


class SurveyMissionCreate(pydantic.BaseModel):
    id: SurveyMissionId
    owner: UserId
    project_id: uuid.UUID
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    relative_path: str
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    links: list[LinkSchema] = []


class SurveyMissionUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    project_id: ProjectId | None = None
    name: LocalizableDraftName | None = None
    description: LocalizableDraftDescription | None = None
    relative_path: str | None = None
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    links: list[LinkSchema] | None = None


class SurveyMissionReadEmbedded(pydantic.BaseModel):
    id: SurveyMissionId
    name: LocalizableDraftName
    status: SurveyMissionStatus
    is_valid: bool
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None
    project: ProjectReadEmbedded

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyMission
    ) -> "SurveyMissionReadEmbedded":
        return cls(
            **instance.model_dump(),
            project=ProjectReadEmbedded.from_db_instance(instance.project),
        )


class SurveyMissionReadListItem(pydantic.BaseModel):
    id: SurveyMissionId
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    status: SurveyMissionStatus
    is_valid: bool
    project: ProjectReadEmbedded

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyMission
    ) -> "SurveyMissionReadListItem":
        return cls(
            **instance.model_dump(),
            project=ProjectReadEmbedded.from_db_instance(instance.project),
        )


class SurveyMissionReadDetail(SurveyMissionReadListItem):
    owner: UserId
    relative_path: str
    links: list[LinkSchema] = []
    bbox_4326: PolygonOut | None

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyMission
    ) -> "SurveyMissionReadDetail":
        return cls(
            **instance.model_dump(),
            project=ProjectReadEmbedded.from_db_instance(instance.project),
        )
