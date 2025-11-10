import datetime as dt

import pydantic
from typing import Annotated

from ..db import models
from ..constants import SurveyRelatedRecordStatus
from .common import (
    DatasetCategoryId,
    DomainTypeId,
    LinkSchema,
    LocalizableDraftDescription,
    LocalizableDraftName,
    PolygonOut,
    PossiblyInvalidPolygon,
    RecordAssetId,
    SurveyMissionId,
    SurveyRelatedRecordId,
    UserId,
    WorkflowStageId,
)
from .surveymissions import SurveyMissionReadEmbedded


class DatasetCategoryCreate(pydantic.BaseModel):
    id: DatasetCategoryId
    name: LocalizableDraftName


class DatasetCategoryRead(pydantic.BaseModel):
    id: DatasetCategoryId
    name: LocalizableDraftName


class DomainTypeCreate(pydantic.BaseModel):
    id: DomainTypeId
    name: LocalizableDraftName


class DomainTypeRead(pydantic.BaseModel):
    id: DomainTypeId
    name: LocalizableDraftName


class WorkflowStageCreate(pydantic.BaseModel):
    id: WorkflowStageId
    name: LocalizableDraftName


class WorkflowStageRead(pydantic.BaseModel):
    id: WorkflowStageId
    name: LocalizableDraftName


class RecordAssetCreate(pydantic.BaseModel):
    id: RecordAssetId
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    relative_path: str
    links: list[LinkSchema] = []


class RecordAssetUpdate(pydantic.BaseModel):
    id: RecordAssetId
    name: LocalizableDraftName | None = None
    description: LocalizableDraftDescription | None = None
    relative_path: str | None = None
    links: list[LinkSchema] | None = None


class RecordAssetReadListItem(pydantic.BaseModel):
    id: RecordAssetId
    name: LocalizableDraftName
    is_valid: bool


class RecordAssetReadDetailEmbedded(RecordAssetReadListItem):
    description: LocalizableDraftDescription
    relative_path: str
    links: list[LinkSchema] = []

    @classmethod
    def from_db_instance(cls, instance: models.RecordAsset) -> "RecordAssetReadDetail":
        return cls(
            **instance.model_dump(),
        )


class SurveyRelatedRecordReadEmbedded(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    name: LocalizableDraftName
    status: SurveyRelatedRecordStatus
    validation_result: models.ValidationResult | None
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None
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
    description: LocalizableDraftDescription
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


def check_asset_english_names_for_uniqueness(
    assets: list[RecordAssetCreate],
) -> list[RecordAssetCreate]:
    seen_names = set()
    for asset in assets:
        if asset.name.en in seen_names:
            raise ValueError(f"Duplicate asset english name found: {asset.name.en!r}")
        seen_names.add(asset.name.en)
    return assets


class SurveyRelatedRecordCreate(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    owner: UserId
    survey_mission_id: SurveyMissionId

    name: LocalizableDraftName
    description: LocalizableDraftDescription
    dataset_category_id: DatasetCategoryId
    domain_type_id: DomainTypeId
    workflow_stage_id: WorkflowStageId
    relative_path: str
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    links: list[LinkSchema] = []
    assets: Annotated[
        list[RecordAssetCreate],
        pydantic.AfterValidator(check_asset_english_names_for_uniqueness),
    ] = []


class SurveyRelatedRecordUpdate(pydantic.BaseModel):
    owner: UserId | None = None
    survey_mission_id: SurveyMissionId | None = None

    name: LocalizableDraftName | None = None
    description: LocalizableDraftDescription | None = None
    dataset_category_id: DatasetCategoryId | None = None
    domain_type_id: DomainTypeId | None = None
    workflow_stage_id: WorkflowStageId | None = None
    relative_path: str | None = None
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    links: list[LinkSchema] | None = None
    assets: Annotated[
        list[RecordAssetUpdate],
        pydantic.AfterValidator(check_asset_english_names_for_uniqueness),
    ] = []


class SurveyRelatedRecordReadListItem(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    status: SurveyRelatedRecordStatus
    validation_result: models.ValidationResult | None
    survey_mission: SurveyMissionReadEmbedded
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyRelatedRecord
    ) -> "SurveyRelatedRecordReadListItem":
        return cls(
            **instance.model_dump(),
            survey_mission=SurveyMissionReadEmbedded.from_db_instance(
                instance.survey_mission
            ),
        )


class SurveyRelatedRecordReadDetail(SurveyRelatedRecordReadListItem):
    owner: UserId
    relative_path: str
    bbox_4326: PolygonOut | None
    links: list[LinkSchema] = []
    survey_mission: SurveyMissionReadEmbedded
    dataset_category: DatasetCategoryRead
    domain_type: DomainTypeRead
    workflow_stage: WorkflowStageRead
    record_assets: list[RecordAssetReadDetailEmbedded]

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyRelatedRecord
    ) -> "SurveyRelatedRecordReadDetail":
        return cls(
            **instance.model_dump(),
            survey_mission=SurveyMissionReadEmbedded.from_db_instance(
                instance.survey_mission
            ),
            dataset_category=DatasetCategoryRead(
                **instance.dataset_category.model_dump()
            ),
            domain_type=DomainTypeRead(**instance.domain_type.model_dump()),
            workflow_stage=WorkflowStageRead(**instance.workflow_stage.model_dump()),
            record_assets=[
                RecordAssetReadDetailEmbedded(**a.model_dump()) for a in instance.assets
            ],
        )
