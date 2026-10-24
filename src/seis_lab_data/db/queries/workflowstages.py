import logging
import uuid

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
    name_filter: str | None = None,
) -> tuple[list[models.WorkflowStage], int | None]:
    limit = page_size
    offset = page_size * (page - 1)
    statement = select(models.WorkflowStage).order_by(models.WorkflowStage.name)
    if name_filter is not None:
        statement = statement.where(models.WorkflowStage.name.ilike(f"%{name_filter}%"))
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_workflow_stages(
    session: AsyncSession,
    name_filter: str | None = None,
) -> list[models.WorkflowStage]:
    statement = select(models.WorkflowStage).order_by(
        func.lower(models.WorkflowStage.name)
    )
    if name_filter is not None:
        statement = statement.where(models.WorkflowStage.name.ilike(f"%{name_filter}%"))
    return (await session.exec(statement)).all()


async def get_workflow_stage(
    session: AsyncSession,
    workflow_stage_id: uuid.UUID,
) -> models.WorkflowStage | None:
    return await session.get(models.WorkflowStage, workflow_stage_id)


async def get_workflow_stage_by_name(
    session: AsyncSession, name: str
) -> models.WorkflowStage | None:
    statement = select(models.WorkflowStage).where(models.WorkflowStage.name == name)
    return (await session.exec(statement)).first()
