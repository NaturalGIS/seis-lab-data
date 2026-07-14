import logging
import datetime as dt
from typing import Annotated

import pydantic

from ..db import models
from ..constants import SurveyRelatedRecordStatus
from .common import (
    LinkSchema,
    LocalizableDraftDescription,
    LocalizableDraftName,
    LocalizableDraftRelationship,
    PolygonOut,
    PossiblyInvalidPolygon,
    serialize_id,
    serialize_possibly_empty_date,
)
from .filters import TemporalExtentFilterValue
from .identifiers import (
    DatasetCategoryId,
    RecordAssetId,
    SurveyRelatedRecordId,
    SurveyMissionId,
    UserId,
    WorkflowStageId,
)
from .surveymissions import SurveyMissionReadEmbedded
from .datasetcategories import DatasetCategoryReadListItem
from .workflowstages import WorkflowStageReadListItem

logger = logging.getLogger(__name__)


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
    id: Annotated[RecordAssetId, pydantic.PlainSerializer(serialize_id)]
    name: LocalizableDraftName
    is_valid: bool


class RecordAssetReadDetailEmbedded(RecordAssetReadListItem):
    description: LocalizableDraftDescription
    relative_path: str
    links: list[LinkSchema] = []


class SurveyRelatedRecordReadEmbedded(pydantic.BaseModel):
    id: Annotated[SurveyRelatedRecordId, pydantic.PlainSerializer(serialize_id)]
    name: LocalizableDraftName
    status: SurveyRelatedRecordStatus
    validation_result: models.ValidationResult | None
    bbox_4326: PolygonOut | None
    temporal_extent_begin: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    temporal_extent_end: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
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


def check_asset_english_names_for_uniqueness(
    assets: list[RecordAssetCreate],
) -> list[RecordAssetCreate]:
    seen_names = set()
    for asset in assets:
        if asset.name.en in seen_names:
            raise ValueError(f"Duplicate asset english name found: {asset.name.en!r}")
        seen_names.add(asset.name.en)
    return assets


class RelatedRecordCreate(pydantic.BaseModel):
    related_record_id: SurveyRelatedRecordId
    relationship: LocalizableDraftRelationship


class SurveyRelatedRecordCreate(pydantic.BaseModel):
    id: SurveyRelatedRecordId
    owner_id: UserId
    survey_mission_id: SurveyMissionId

    name: LocalizableDraftName
    description: LocalizableDraftDescription
    dataset_category_id: DatasetCategoryId
    workflow_stage_id: WorkflowStageId
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    links: list[LinkSchema] = []
    assets: Annotated[
        list[RecordAssetCreate],
        pydantic.AfterValidator(check_asset_english_names_for_uniqueness),
    ] = []
    related_records: list[RelatedRecordCreate] = []
    extra_properties: dict[str, str] | None = None


class SurveyRelatedRecordBulkUpdate(pydantic.BaseModel):
    description: LocalizableDraftDescription | None = None
    dataset_category_id: DatasetCategoryId | None = None
    workflow_stage_id: WorkflowStageId | None = None
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    related_records: list[RelatedRecordCreate] = []


class SurveyRelatedRecordBulkUpdateSelection(pydantic.BaseModel):
    """Which records a bulk update targets.

    `selected` and the filter/`excluded_record_ids` fields are mutually
    exclusive ways of specifying the target records, mirroring the two
    selection modes offered by the UI - see
    `operations.surveyrelatedrecords.bulk_update_survey_related_records`.

    `survey_mission_id` is an optional additional scope, not a requirement -
    callers that aren't scoped to a single mission (e.g. a future bulk-edit
    entry point on the general record listing) can simply omit it.
    """

    selected: list[SurveyRelatedRecordId] | None = None
    excluded_record_ids: list[SurveyRelatedRecordId] | None = None
    survey_mission_id: SurveyMissionId | None = None
    en_name_filter: str | None = None
    pt_name_filter: str | None = None
    spatial_intersect: PossiblyInvalidPolygon | None = None
    temporal_extent: TemporalExtentFilterValue | None = None
    asset_path_fragment_filter: str | None = None


class SurveyRelatedRecordUpdate(pydantic.BaseModel):
    owner_id: UserId | None = None
    survey_mission_id: SurveyMissionId | None = None

    name: LocalizableDraftName | None = None
    description: LocalizableDraftDescription | None = None
    dataset_category_id: DatasetCategoryId | None = None
    workflow_stage_id: WorkflowStageId | None = None
    bbox_4326: PossiblyInvalidPolygon | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None
    links: list[LinkSchema] | None = None
    assets: Annotated[
        list[RecordAssetUpdate],
        pydantic.AfterValidator(check_asset_english_names_for_uniqueness),
    ] = []
    related_records: list[RelatedRecordCreate] = []


class SurveyRelatedRecordReadListItem(pydantic.BaseModel):
    id: Annotated[SurveyRelatedRecordId, pydantic.PlainSerializer(serialize_id)]
    name: LocalizableDraftName
    description: LocalizableDraftDescription
    status: SurveyRelatedRecordStatus
    validation_result: models.ValidationResult | None
    survey_mission: SurveyMissionReadEmbedded
    dataset_category: DatasetCategoryReadListItem
    workflow_stage: WorkflowStageReadListItem
    bbox_4326: PolygonOut | None
    temporal_extent_begin: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]
    temporal_extent_end: Annotated[
        dt.date | None, pydantic.PlainSerializer(serialize_possibly_empty_date)
    ]

    @classmethod
    def from_db_instance(
        cls, instance: models.SurveyRelatedRecord
    ) -> "SurveyRelatedRecordReadListItem":
        return cls(
            **instance.model_dump(),
            survey_mission=SurveyMissionReadEmbedded.from_db_instance(
                instance.survey_mission
            ),
            dataset_category=DatasetCategoryReadListItem.model_validate(
                instance.dataset_category, from_attributes=True
            ),
            workflow_stage=WorkflowStageReadListItem.model_validate(
                instance.workflow_stage, from_attributes=True
            ),
        )


class SurveyRelatedRecordReadDetail(SurveyRelatedRecordReadListItem):
    owner_id: UserId
    links: list[LinkSchema] = []
    survey_mission: SurveyMissionReadEmbedded
    # dataset_category: DatasetCategoryReadListItem
    # workflow_stage: WorkflowStageReadListItem
    record_assets: list[RecordAssetReadDetailEmbedded]
    related_to_records: list[
        tuple[LocalizableDraftDescription, SurveyRelatedRecordReadEmbedded]
    ]
    subject_for_records: list[
        tuple[LocalizableDraftDescription, SurveyRelatedRecordReadEmbedded]
    ]

    @classmethod
    def from_db_instance(
        cls,
        instance: models.SurveyRelatedRecord,
        records_related_to: list[tuple[dict, models.SurveyRelatedRecord]],
        records_subject_for: list[tuple[dict, models.SurveyRelatedRecord]],
    ) -> "SurveyRelatedRecordReadDetail":
        return cls(
            **instance.model_dump(),
            survey_mission=SurveyMissionReadEmbedded.from_db_instance(
                instance.survey_mission
            ),
            dataset_category=DatasetCategoryReadListItem.model_validate(
                instance.dataset_category, from_attributes=True
            ),
            workflow_stage=WorkflowStageReadListItem.model_validate(
                instance.workflow_stage, from_attributes=True
            ),
            record_assets=[
                RecordAssetReadDetailEmbedded.model_validate(
                    db_asset, from_attributes=True
                )
                for db_asset in instance.assets
            ],
            related_to_records=[
                (relation, SurveyRelatedRecordReadEmbedded.from_db_instance(record))
                for relation, record in records_related_to
            ],
            subject_for_records=[
                (relation, SurveyRelatedRecordReadEmbedded.from_db_instance(record))
                for relation, record in records_subject_for
            ],
        )
