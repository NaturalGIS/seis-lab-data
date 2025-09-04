from typing import TYPE_CHECKING

import pydantic

from ..db import models
from ..constants import SurveyRelatedRecordStatus
from .common import (
    AtLeastEnglishName,
    AtLeastEnglishDescription,
    DatasetCategoryId,
    DomainTypeId,
    LinkSchema,
    RecordAssetId,
    SurveyMissionId,
    SurveyRelatedRecordId,
    UserId,
    WorkflowStageId,
)
from .surveymissions import SurveyMissionReadEmbedded

if TYPE_CHECKING:
    from .recordassets import RecordAssetCreate


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


class RecordAssetCreate(pydantic.BaseModel):
    id: RecordAssetId
    name: AtLeastEnglishName
    description: AtLeastEnglishDescription
    relative_path: str
    links: list[LinkSchema] = []


class RecordAssetUpdate(pydantic.BaseModel):
    name: AtLeastEnglishName | None = None
    description: AtLeastEnglishDescription | None = None
    relative_path: str | None = None
    links: list[LinkSchema] | None = None


class RecordAssetReadListItem(pydantic.BaseModel):
    id: RecordAssetId
    name: AtLeastEnglishName
    is_valid: bool


class RecordAssetReadDetailEmbedded(RecordAssetReadListItem):
    description: AtLeastEnglishDescription
    relative_path: str
    links: list[LinkSchema] = []

    @classmethod
    def from_db_instance(cls, instance: models.RecordAsset) -> "RecordAssetReadDetail":
        return cls(
            **instance.model_dump(),
        )


class SurveyRelatedRecordReadEmbedded(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    slug: str
    name: AtLeastEnglishName
    status: SurveyRelatedRecordStatus
    is_valid: bool
    survey_mission: SurveyMissionReadEmbedded

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyRelatedRecord
    ) -> "SurveyRelatedRecordReadEmbedded":
        return cls(
            **instance.model_dump(),
            survey_mission=SurveyMissionReadEmbedded.from_db_instance(
                instance.survey_mission
            ),
        )


class RecordAssetReadDetail(RecordAssetReadListItem):
    survey_related_record: SurveyRelatedRecordReadEmbedded
    description: AtLeastEnglishDescription
    relative_path: str
    links: list[LinkSchema] = []

    @classmethod
    def from_db_instance(cls, instance: models.RecordAsset) -> "RecordAssetReadDetail":
        return cls(
            **instance.model_dump(),
            survey_related_record=SurveyRelatedRecordReadEmbedded.from_db_instance(
                instance.survey_related_record
            ),
        )


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
    assets: list[RecordAssetCreate] = []


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
    survey_mission: SurveyMissionReadEmbedded
    dataset_category: DatasetCategoryRead
    domain_type: DomainTypeRead
    workflow_stage: WorkflowStageRead
    record_assets: list[RecordAssetReadDetailEmbedded]

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyRelatedRecord, assets: list[models.RecordAsset]
    ) -> "SurveyRelatedRecordReadDetail":
        return cls(
            **instance.model_dump(),
            survey_mission=SurveyMissionReadEmbedded.from_db_instance(
                instance.survey_mission
            ),
            dataset_category=instance.dataset_category.model_dump(),
            domain_type=instance.domain_type.model_dump(),
            workflow_stage=instance.workflow_stage.model_dump(),
            record_assets=[
                RecordAssetReadDetailEmbedded(**a.model_dump()) for a in assets
            ],
        )
