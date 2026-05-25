import logging
import uuid
from typing import Protocol

import shapely
from anyio import Path
from sqlmodel.ext.asyncio.session import AsyncSession

from ..db import models
from ..db.queries import surveyrelatedrecords as record_queries
from ..processing.extractors import dispatch_extractor
from ..schemas import (
    DatasetCategoryId,
    DomainTypeId,
    LocalizableDraftDescription,
    LocalizableDraftName,
    RecordAssetCreate,
    SurveyMissionId,
    SurveyRelatedRecordCreate,
    SurveyRelatedRecordId,
    UserId,
    WorkflowStageId,
)
from ..schemas import discovery as discovery_schemas
from ..schemas import surveyrelatedrecords as record_schemas

logger = logging.getLogger(__name__)


DiscoveredAsset = tuple[RecordAssetCreate, Path]


class RecordExtractorProtocol(Protocol):
    async def __call__(
        self,
        *,
        survey_mission: models.SurveyMission,
        record_configuration: discovery_schemas.SurveyRecordDiscoveryConfiguration,
        discovered_assets: list[DiscoveredAsset],
        session: AsyncSession,
    ) -> record_schemas.SurveyRelatedRecordCreate:
        """Assemble a SurveyRelatedRecordCreate from discovered files."""


async def extractor1(
    *,
    survey_mission: models.SurveyMission,
    record_configuration: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    discovered_assets: list[DiscoveredAsset],
    session: AsyncSession,
) -> record_schemas.SurveyRelatedRecordCreate:
    if not discovered_assets:
        raise ValueError("extractor1 requires at least one discovered asset")

    bboxes: list[tuple[float, float, float, float]] = []
    for _, abs_path in discovered_assets:
        metadata = dispatch_extractor(abs_path)
        if metadata is not None and metadata.bbox_4326 is not None:
            bboxes.append(metadata.bbox_4326)

    bbox_wkt = _aggregate_bbox_wkt(bboxes)

    dataset_category = await record_queries.get_dataset_category_by_english_name(
        session, record_configuration.dataset_category
    )
    domain_type = await record_queries.get_domain_type_by_english_name(
        session, record_configuration.domain_type
    )
    workflow_stage = await record_queries.get_workflow_stage_by_english_name(
        session, record_configuration.workflow_stage
    )
    if dataset_category is None:
        raise ValueError(
            f"Unknown dataset_category {record_configuration.dataset_category!r}"
        )
    if domain_type is None:
        raise ValueError(f"Unknown domain_type {record_configuration.domain_type!r}")
    if workflow_stage is None:
        raise ValueError(
            f"Unknown workflow_stage {record_configuration.workflow_stage!r}"
        )

    relative_path = "/".join(
        (
            record_configuration.domain_type,
            record_configuration.dataset_category,
            record_configuration.workflow_stage,
        )
    )

    return SurveyRelatedRecordCreate(
        id=SurveyRelatedRecordId(uuid.uuid4()),
        owner_id=UserId(survey_mission.owner_id),
        survey_mission_id=SurveyMissionId(survey_mission.id),
        name=LocalizableDraftName(**record_configuration.name),
        description=LocalizableDraftDescription(
            **(record_configuration.description or {})
        ),
        dataset_category_id=DatasetCategoryId(dataset_category.id),
        domain_type_id=DomainTypeId(domain_type.id),
        workflow_stage_id=WorkflowStageId(workflow_stage.id),
        relative_path=relative_path,
        bbox_4326=bbox_wkt,
        temporal_extent_begin=None,
        temporal_extent_end=None,
        links=list(record_configuration.links),
        assets=[asset for asset, _ in discovered_assets],
        related_records=[],
    )


def _aggregate_bbox_wkt(
    bboxes: list[tuple[float, float, float, float]],
) -> str | None:
    if not bboxes:
        return None
    polys = [shapely.box(minx, miny, maxx, maxy) for minx, miny, maxx, maxy in bboxes]
    union = shapely.unary_union(polys)
    minx, miny, maxx, maxy = union.bounds
    return shapely.box(minx, miny, maxx, maxy).wkt
