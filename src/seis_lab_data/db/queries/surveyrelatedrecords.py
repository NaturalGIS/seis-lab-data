import logging

import shapely
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    exists,
    func,
    or_,
    select,
)

from ...constants import SurveyRelatedRecordStatus
from ...db import models
from ...schemas import (
    identifiers,
    filters as filter_schemas,
)
from .common import _get_total_num_records

logger = logging.getLogger(__name__)


def _build_survey_related_record_statement(
    survey_mission_id: identifiers.SurveyMissionId | None = None,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: filter_schemas.TemporalExtentFilterValue | None = None,
    asset_path_fragment_filter: str | None = None,
):
    statement = (
        select(models.SurveyRelatedRecord)
        .options(
            selectinload(models.SurveyRelatedRecord.survey_mission).selectinload(
                models.SurveyMission.project
            )
        )
        .options(selectinload(models.SurveyRelatedRecord.dataset_category))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
    )
    if en_name_filter:
        statement = statement.where(
            models.SurveyRelatedRecord.name["en"].astext.ilike(f"%{en_name_filter}%")
        )
    if pt_name_filter:
        statement = statement.where(
            models.SurveyRelatedRecord.name["pt"].astext.ilike(f"%{pt_name_filter}%")
        )
    if spatial_intersect is not None:
        statement = statement.where(
            or_(
                func.ST_Intersects(
                    models.SurveyRelatedRecord.bbox_4326,
                    func.ST_GeomFromText(spatial_intersect.wkt, 4326),
                ),
                models.SurveyRelatedRecord.bbox_4326.is_(None),
            )
        )
    if survey_mission_id is not None:
        statement = statement.where(
            models.SurveyRelatedRecord.survey_mission_id == survey_mission_id
        )
    if temporal_extent is not None:
        if temporal_extent.begin is not None:
            statement = statement.where(
                models.SurveyRelatedRecord.temporal_extent_begin
                >= temporal_extent.begin
            )
        if temporal_extent.end is not None:
            statement = statement.where(
                models.SurveyRelatedRecord.temporal_extent_end <= temporal_extent.end
            )
    if asset_path_fragment_filter is not None:
        statement = statement.where(
            exists(
                select(models.RecordAsset)
                .where(
                    models.RecordAsset.survey_related_record_id
                    == models.SurveyRelatedRecord.id
                )
                .where(
                    models.RecordAsset.relative_path.ilike(
                        f"%{asset_path_fragment_filter}%"
                    )
                )
            )
        )
    return statement.order_by(
        models.SurveyRelatedRecord.temporal_extent_end.desc().nullslast()
    ).order_by(models.SurveyRelatedRecord.temporal_extent_begin.desc().nullslast())


async def _exec_survey_related_record_list(
    session: AsyncSession,
    statement,
    limit: int,
    offset: int,
    include_total: bool,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def list_published_survey_related_records(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: filter_schemas.TemporalExtentFilterValue | None = None,
    asset_path_fragment_filter: str | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    statement = _build_survey_related_record_statement(
        survey_mission_id,
        en_name_filter,
        pt_name_filter,
        spatial_intersect,
        temporal_extent,
        asset_path_fragment_filter,
    ).where(models.SurveyRelatedRecord.status == SurveyRelatedRecordStatus.PUBLISHED)
    limit = page_size
    offset = page_size * (page - 1)
    return await _exec_survey_related_record_list(
        session, statement, limit, offset, include_total
    )


async def list_accessible_survey_related_records(
    session: AsyncSession,
    user_id: str,
    survey_mission_id: identifiers.SurveyMissionId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: filter_schemas.TemporalExtentFilterValue | None = None,
    asset_path_fragment_filter: str | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    statement = (
        _build_survey_related_record_statement(
            survey_mission_id,
            en_name_filter,
            pt_name_filter,
            spatial_intersect,
            temporal_extent,
            asset_path_fragment_filter,
        )
        .join(
            models.SurveyMission,
            models.SurveyRelatedRecord.survey_mission_id == models.SurveyMission.id,
        )
        .join(models.Project, models.SurveyMission.project_id == models.Project.id)
        .where(
            or_(
                models.SurveyRelatedRecord.status
                == SurveyRelatedRecordStatus.PUBLISHED,
                models.SurveyRelatedRecord.owner == user_id,
                models.SurveyMission.owner == user_id,
                models.Project.owner == user_id,
            )
        )
    )
    limit = page_size
    offset = page_size * (page - 1)
    return await _exec_survey_related_record_list(
        session, statement, limit, offset, include_total
    )


async def list_survey_related_records(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: filter_schemas.TemporalExtentFilterValue | None = None,
    asset_path_fragment_filter: str | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    """Return all records regardless of status. Intended for admin use."""
    statement = _build_survey_related_record_statement(
        survey_mission_id,
        en_name_filter,
        pt_name_filter,
        spatial_intersect,
        temporal_extent,
        asset_path_fragment_filter,
    )
    limit = page_size
    offset = page_size * (page - 1)
    return await _exec_survey_related_record_list(
        session, statement, limit, offset, include_total
    )


async def get_survey_related_record(
    session: AsyncSession,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
) -> models.SurveyRelatedRecord | None:
    statement = (
        select(models.SurveyRelatedRecord)
        .where(models.SurveyRelatedRecord.id == survey_related_record_id)
        .options(
            selectinload(models.SurveyRelatedRecord.survey_mission).selectinload(
                models.SurveyMission.project
            )
        )
        .options(selectinload(models.SurveyRelatedRecord.dataset_category))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
        # adding all assets too, since they will always be a small list
        .options(selectinload(models.SurveyRelatedRecord.assets))
        # also adding relationships with other records - only first order relationships are loaded, not the full tree
        .options(selectinload(models.SurveyRelatedRecord.related_to_links))
        .options(selectinload(models.SurveyRelatedRecord.subject_links))
    )
    return (await session.exec(statement)).first()


async def get_survey_related_record_by_english_name(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
    english_name: str,
) -> models.SurveyRelatedRecord | None:
    statement = (
        select(models.SurveyRelatedRecord)
        .where(models.SurveyRelatedRecord.survey_mission_id == survey_mission_id)
        .where(models.SurveyRelatedRecord.name["en"].astext == english_name)
        .options(
            selectinload(models.SurveyRelatedRecord.survey_mission).selectinload(
                models.SurveyMission.project
            )
        )
        .options(selectinload(models.SurveyRelatedRecord.dataset_category))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
        # adding all assets too, since they will always be a small list
        .options(selectinload(models.SurveyRelatedRecord.assets))
        # also adding relationships with other records - only first order relationships are loaded, not the full tree
        .options(selectinload(models.SurveyRelatedRecord.related_to_links))
        .options(selectinload(models.SurveyRelatedRecord.subject_links))
    )
    return (await session.exec(statement)).first()


async def list_survey_related_record_related_to_records(
    session: AsyncSession,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[dict, models.SurveyRelatedRecord]]:
    """Return records in which the input id is a subject of a relation.

    Returned records are those which are related to the input id.
    """
    statement = (
        select(
            models.SurveyRelatedRecordSelfLink.relation,
            models.SurveyRelatedRecord,
        )
        .join(
            models.SurveyRelatedRecordSelfLink,
            models.SurveyRelatedRecordSelfLink.related_to_id
            == models.SurveyRelatedRecord.id,
        )
        .where(
            models.SurveyRelatedRecordSelfLink.subject_id == survey_related_record_id
        )
        .options(
            selectinload(models.SurveyRelatedRecord.survey_mission).selectinload(
                models.SurveyMission.project
            )
        )
        .options(selectinload(models.SurveyRelatedRecord.dataset_category))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
    )
    return (await session.exec(statement.offset(offset).limit(limit))).all()


async def list_survey_related_record_subject_records(
    session: AsyncSession,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[dict, models.SurveyRelatedRecord]]:
    """Return records which are subjects in a relation with the input id.

    Returned records are those which are subjects in a relation where the input id is involved
    """
    statement = (
        select(
            models.SurveyRelatedRecordSelfLink.relation,
            models.SurveyRelatedRecord,
        )
        .join(
            models.SurveyRelatedRecordSelfLink,
            models.SurveyRelatedRecordSelfLink.subject_id
            == models.SurveyRelatedRecord.id,
        )
        .where(
            models.SurveyRelatedRecordSelfLink.related_to_id == survey_related_record_id
        )
        .options(
            selectinload(models.SurveyRelatedRecord.survey_mission).selectinload(
                models.SurveyMission.project
            )
        )
        .options(selectinload(models.SurveyRelatedRecord.dataset_category))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
    )
    return (await session.exec(statement.offset(offset).limit(limit))).all()
