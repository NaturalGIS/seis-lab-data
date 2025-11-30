import logging
import uuid

import shapely
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    func,
    or_,
    select,
)

from ... import schemas
from ...db import models
from .common import _get_total_num_records

logger = logging.getLogger(__name__)


async def paginated_list_survey_related_records(
    session: AsyncSession,
    user: schemas.User | None = None,
    survey_mission_id: schemas.SurveyMissionId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    limit = page_size
    offset = limit * (page - 1)
    return await list_survey_related_records(
        session,
        user,
        survey_mission_id,
        limit,
        offset,
        include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
        temporal_extent=temporal_extent,
    )


async def list_survey_related_records(
    session: AsyncSession,
    user: schemas.User | None = None,
    survey_mission_id: schemas.SurveyMissionId | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.SurveyRelatedRecord], int | None]:
    statement = (
        select(models.SurveyRelatedRecord)
        .options(
            selectinload(models.SurveyRelatedRecord.survey_mission).selectinload(
                models.SurveyMission.project
            )
        )
        .options(selectinload(models.SurveyRelatedRecord.dataset_category))
        .options(selectinload(models.SurveyRelatedRecord.domain_type))
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
    statement = statement.order_by(
        models.SurveyRelatedRecord.temporal_extent_end.desc().nullslast()
    ).order_by(models.SurveyRelatedRecord.temporal_extent_begin.desc().nullslast())
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def get_survey_related_record(
    session: AsyncSession,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
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
        .options(selectinload(models.SurveyRelatedRecord.domain_type))
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
    survey_mission_id: schemas.SurveyMissionId,
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
        .options(selectinload(models.SurveyRelatedRecord.domain_type))
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
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[str, models.SurveyRelatedRecord]]:
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
        .options(selectinload(models.SurveyRelatedRecord.domain_type))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
    )
    return (await session.exec(statement.offset(offset).limit(limit))).all()


async def list_survey_related_record_subject_records(
    session: AsyncSession,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[str, models.SurveyRelatedRecord]]:
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
        .options(selectinload(models.SurveyRelatedRecord.domain_type))
        .options(selectinload(models.SurveyRelatedRecord.workflow_stage))
    )
    return (await session.exec(statement.offset(offset).limit(limit))).all()


async def list_dataset_categories(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    order_by_clause=models.DatasetCategory.name["en"].astext,
) -> tuple[list[models.DatasetCategory], int | None]:
    # NOTE: limit, offset and order_by are applied only when asking the
    # session to exec because we want to reuse the statement later, to count
    # total number of records
    statement = select(models.DatasetCategory)
    items = (
        await session.exec(
            statement.limit(limit).offset(offset).order_by(order_by_clause)
        )
    ).all()

    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_dataset_categories(
    session: AsyncSession, order_by_clause=models.DatasetCategory.name["en"].astext
) -> list[models.DatasetCategory]:
    _, num_total = await list_dataset_categories(session, limit=1, include_total=True)
    items, _ = await list_dataset_categories(
        session, limit=num_total, include_total=False, order_by_clause=order_by_clause
    )
    return items


async def get_dataset_category(
    session: AsyncSession,
    dataset_category_id: uuid.UUID,
) -> models.DatasetCategory | None:
    return await session.get(models.DatasetCategory, dataset_category_id)


async def get_dataset_category_by_english_name(
    session: AsyncSession, name: str
) -> models.DatasetCategory | None:
    statement = select(models.DatasetCategory).where(
        models.DatasetCategory.name["en"].astext == name
    )
    return (await session.exec(statement)).first()


async def list_domain_types(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    order_by_clause=models.DomainType.name["en"].astext,
) -> tuple[list[models.DomainType], int | None]:
    statement = select(models.DomainType)

    # NOTE: limit, offset and order_by are applied only when asking the
    # session to exec because we want to reuse the statement later, to count
    # total number of records
    items = (
        await session.exec(
            statement.offset(offset).limit(limit).order_by(order_by_clause)
        )
    ).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_domain_types(
    session: AsyncSession, order_by_clause=models.DomainType.name["en"].astext
) -> list[models.DomainType]:
    _, num_total = await list_domain_types(session, limit=1, include_total=True)
    items, _ = await list_domain_types(
        session, limit=num_total, include_total=False, order_by_clause=order_by_clause
    )
    return items


async def get_domain_type(
    session: AsyncSession,
    domain_type_id: uuid.UUID,
) -> models.DomainType | None:
    return await session.get(models.DomainType, domain_type_id)


async def get_domain_type_by_english_name(
    session: AsyncSession, name: str
) -> models.DomainType | None:
    statement = select(models.DomainType).where(
        models.DomainType.name["en"].astext == name
    )
    return (await session.exec(statement)).first()


async def list_workflow_stages(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    order_by_clause=models.WorkflowStage.name["en"].astext,
) -> tuple[list[models.WorkflowStage], int | None]:
    statement = select(models.WorkflowStage)

    # NOTE: limit, offset and order_by are applied only when asking the
    # session to exec because we want to reuse the statement later, to count
    # total number of records
    items = (
        await session.exec(
            statement.offset(offset).limit(limit).order_by(order_by_clause)
        )
    ).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_workflow_stages(
    session: AsyncSession, order_by_clause=models.WorkflowStage.name["en"].astext
) -> list[models.WorkflowStage]:
    _, num_total = await list_workflow_stages(session, limit=1, include_total=True)
    items, _ = await list_workflow_stages(
        session, limit=num_total, include_total=False, order_by_clause=order_by_clause
    )
    return items


async def get_workflow_stage(
    session: AsyncSession,
    workflow_stage_id: uuid.UUID,
) -> models.WorkflowStage | None:
    return await session.get(models.WorkflowStage, workflow_stage_id)


async def get_workflow_stage_by_english_name(
    session: AsyncSession, name: str
) -> models.WorkflowStage | None:
    statement = select(models.WorkflowStage).where(
        models.WorkflowStage.name["en"].astext == name
    )
    return (await session.exec(statement)).first()
