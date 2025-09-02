import uuid

import pydantic

from .common import (
    AtLeastEnglishDescription,
    AtLeastEnglishName,
    LinkSchema,
    ProjectId,
    SurveyMissionId,
    UserId,
)
from ..constants import SurveyMissionStatus


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
