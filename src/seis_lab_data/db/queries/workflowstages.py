import logging
import uuid
from typing import Literal

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    func,
    select,
)

from ...db import models
from .common import _get_total_num_records

logger = logging.getLogger(__name__)


async def list_workflow_stages(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
) -> tuple[list[models.WorkflowStage], int | None]:
    limit = page_size
    offset = page_size * (page - 1)
    statement = select(models.WorkflowStage).order_by(
        models.WorkflowStage.name["en"].astext
    )
    if en_name_filter is not None:
        statement = statement.where(
            models.WorkflowStage.name["en"].astext.ilike(f"%{en_name_filter}%")
        )
    if pt_name_filter is not None:
        statement = statement.where(
            models.WorkflowStage.name["pt"].astext.ilike(f"%{pt_name_filter}%")
        )
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_workflow_stages(
    session: AsyncSession,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    order_by: Literal["name_en", "name_pt"] = "name_en",
) -> list[models.WorkflowStage]:
    order_by_clause = {
        "name_pt": func.lower(models.WorkflowStage.name["pt"].astext),
    }.get(order_by, func.lower(models.WorkflowStage.name["en"].astext))

    statement = select(models.WorkflowStage).order_by(order_by_clause)
    if en_name_filter is not None:
        statement = statement.where(
            models.WorkflowStage.name["en"].astext.ilike(f"%{en_name_filter}%")
        )
    if pt_name_filter is not None:
        statement = statement.where(
            models.WorkflowStage.name["pt"].astext.ilike(f"%{pt_name_filter}%")
        )
    return (await session.exec(statement)).all()


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
