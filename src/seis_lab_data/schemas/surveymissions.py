import uuid

import pydantic

from ..constants import SurveyMissionStatus
from ..db import models
from .common import (
    AtLeastEnglishDescription,
    AtLeastEnglishName,
    LinkSchema,
    ProjectId,
    SurveyMissionId,
    UserId,
)
from .projects import ProjectReadEmbedded


class SurveyMissionCreate(pydantic.BaseModel):
    id: SurveyMissionId
    owner: UserId
    project_id: uuid.UUID
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    relative_path: str
    links: list[LinkSchema] = []


class SurveyMissionUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    project_id: ProjectId | None = None
    name: AtLeastEnglishName | None = None
    description: AtLeastEnglishDescription | None = None
    relative_path: str | None = None
    links: list[LinkSchema] | None = None


class SurveyMissionReadEmbedded(pydantic.BaseModel):
    id: SurveyMissionId
    slug: str
    name: AtLeastEnglishName
    status: SurveyMissionStatus
    is_valid: bool
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
    slug: str
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    status: SurveyMissionStatus
    is_valid: bool


class SurveyMissionReadDetail(SurveyMissionReadListItem):
    owner: UserId
    relative_path: str
    links: list[LinkSchema] = []
    project: ProjectReadEmbedded

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyMission
    ) -> "SurveyMissionReadDetail":
        return cls(
            **instance.model_dump(),
            project=ProjectReadEmbedded.from_db_instance(instance.project),
        )
