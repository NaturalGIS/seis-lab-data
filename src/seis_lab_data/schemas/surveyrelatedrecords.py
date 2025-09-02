import pydantic

from ..constants import SurveyRelatedRecordStatus
from .common import (
    AtLeastEnglishName,
    AtLeastEnglishDescription,
    DatasetCategoryId,
    DomainTypeId,
    LinkSchema,
    SurveyMissionId,
    SurveyRelatedRecordId,
    UserId,
    WorkflowStageId,
)


class DatasetCategoryCreate(pydantic.BaseModel):
    id: DatasetCategoryId
    name: AtLeastEnglishName


class DatasetCategoryRead(pydantic.BaseModel):
    id: DatasetCategoryId
    name: AtLeastEnglishName


class DomainTypeCreate(pydantic.BaseModel):
    id: DomainTypeId
    name: AtLeastEnglishName


class DomainTypeRead(pydantic.BaseModel):
    id: DomainTypeId
    name: AtLeastEnglishName


class WorkflowStageCreate(pydantic.BaseModel):
    id: WorkflowStageId
    name: AtLeastEnglishName


class WorkflowStageRead(pydantic.BaseModel):
    id: WorkflowStageId
    name: AtLeastEnglishName


class SurveyRelatedRecordCreate(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    owner: UserId
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    survey_mission_id: SurveyMissionId
    dataset_category_id: DatasetCategoryId
    domain_type_id: DomainTypeId
    workflow_stage_id: WorkflowStageId
    relative_path: str
    links: list[LinkSchema] = []


class SurveyRelatedRecordUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    name: AtLeastEnglishName | None = None
    description: AtLeastEnglishDescription | None = None
    survey_mission_id: SurveyMissionId | None = None
    dataset_category_id: DatasetCategoryId | None = None
    domain_type_id: DomainTypeId | None = None
    workflow_stage_id: WorkflowStageId | None = None
    relative_path: str | None = None
    links: list[LinkSchema] | None = None


class SurveyRelatedRecordReadListItem(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    slug: str
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    status: SurveyRelatedRecordStatus
    is_valid: bool


class SurveyRelatedRecordReadDetail(SurveyRelatedRecordReadListItem):
    owner: UserId
    relative_path: str
    links: list[LinkSchema] = []
