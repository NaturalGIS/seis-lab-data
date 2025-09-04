from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ... import schemas
from ...db import models
from .common import _get_total_num_records

_SELECT_IN_LOAD_OPTIONS = (
    selectinload(models.RecordAsset.survey_related_record)
    .selectinload(models.SurveyRelatedRecord.survey_mission)
    .selectinload(models.SurveyMission.project)
)


async def collect_all_record_assets(
    session: AsyncSession,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
) -> list[models.RecordAsset]:
    statement = (
        select(models.RecordAsset)
        .where(models.RecordAsset.survey_related_record_id == survey_related_record_id)
        .options(_SELECT_IN_LOAD_OPTIONS)
    )
    return (await session.exec(statement)).all()


async def list_record_assets(
    session: AsyncSession,
    survey_related_record_id: schemas.SurveyRelatedRecordId,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.RecordAsset], int | None]:
    statement = (
        select(models.RecordAsset)
        .where(models.RecordAsset.survey_related_record_id == survey_related_record_id)
        .options(_SELECT_IN_LOAD_OPTIONS)
    )
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def get_record_asset(
    session: AsyncSession,
    record_asset_id: schemas.RecordAssetId,
) -> models.RecordAsset | None:
    statement = (
        select(models.RecordAsset)
        .where(models.RecordAsset.id == record_asset_id)
        .options(_SELECT_IN_LOAD_OPTIONS)
    )
    return (await session.exec(statement)).first()
