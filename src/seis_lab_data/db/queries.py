import uuid

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import (
    func,
    select,
)

from . import models


async def _get_total_num_records(session: AsyncSession, statement):
    return (await session.exec(select(func.count()).select_from(statement))).first()


async def list_projects(
    session: AsyncSession,
    user: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.Project], int | None]:
    statement = select(models.Project)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_projects(
    session: AsyncSession,
) -> list[models.Project]:
    _, num_total = await list_projects(session, limit=1, include_total=True)
    items, _ = await list_projects(session, limit=num_total, include_total=False)
    return items


async def get_project(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> models.Project | None:
    return await session.get(models.Project, project_id)


async def get_project_by_slug(
    session: AsyncSession, slug: str
) -> models.Project | None:
    statement = select(models.Project).where(models.Project.slug == slug)
    return (await session.exec(statement)).first()


async def list_dataset_categories(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.DatasetCategory], int | None]:
    statement = select(models.DatasetCategory)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_dataset_categories(
    session: AsyncSession,
) -> list[models.DatasetCategory]:
    _, num_total = await list_dataset_categories(session, limit=1, include_total=True)
    items, _ = await list_dataset_categories(
        session, limit=num_total, include_total=False
    )
    return items


async def get_dataset_category(
    session: AsyncSession,
    dataset_category_id: uuid.UUID,
) -> models.DatasetCategory | None:
    return await session.get(models.DatasetCategory, dataset_category_id)


async def list_domain_types(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.DomainType], int | None]:
    statement = select(models.DomainType)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_domain_types(
    session: AsyncSession,
) -> list[models.DomainType]:
    _, num_total = await list_domain_types(session, limit=1, include_total=True)
    items, _ = await list_domain_types(session, limit=num_total, include_total=False)
    return items


async def get_domain_type(
    session: AsyncSession,
    domain_type_id: uuid.UUID,
) -> models.DomainType | None:
    return await session.get(models.DomainType, domain_type_id)


async def list_workflow_stages(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.WorkflowStage], int | None]:
    statement = select(models.WorkflowStage)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def collect_all_workflow_stages(
    session: AsyncSession,
) -> list[models.WorkflowStage]:
    _, num_total = await list_workflow_stages(session, limit=1, include_total=True)
    items, _ = await list_workflow_stages(session, limit=num_total, include_total=False)
    return items


async def get_workflow_stage(
    session: AsyncSession,
    workflow_stage_id: uuid.UUID,
) -> models.WorkflowStage | None:
    return await session.get(models.WorkflowStage, workflow_stage_id)
