import datetime as dt
from typing import Annotated

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
    serialize_id,
    serialize_possibly_empty_date,
    SurveyMissionId,
    UserId,
)
from .projects import ProjectReadEmbedded


class SurveyMissionCreate(pydantic.BaseModel):
    id: SurveyMissionId
    owner: UserId
    project_id: ProjectId
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
    id: Annotated[SurveyMissionId, pydantic.PlainSerializer(serialize_id)]
    name: LocalizableDraftName
    status: SurveyMissionStatus
    validation_result: models.ValidationResult | None
    relative_path: str
    temporal_extent_begin: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    temporal_extent_end: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    project: ProjectReadEmbedded
    bbox_4326: PolygonOut | None
    num_survey_related_records: int

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyMission
    ) -> "SurveyMissionReadEmbedded":
        return cls(
            **instance.model_dump(),
            project=ProjectReadEmbedded.from_db_instance(instance.project),
        )


class SurveyMissionReadListItem(pydantic.BaseModel):
    id: Annotated[SurveyMissionId, pydantic.PlainSerializer(serialize_id)]
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    status: SurveyMissionStatus
    validation_result: models.ValidationResult | None
    project: ProjectReadEmbedded
    temporal_extent_begin: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    temporal_extent_end: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    bbox_4326: PolygonOut | None
    num_survey_related_records: int

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

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyMission
    ) -> "SurveyMissionReadDetail":
        return cls(
            **instance.model_dump(),
            project=ProjectReadEmbedded.from_db_instance(instance.project),
        )
