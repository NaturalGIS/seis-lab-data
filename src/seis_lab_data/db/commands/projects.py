import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import (
    errors,
    schemas,
)
from .. import (
    models,
    queries,
)

logger = logging.getLogger(__name__)


async def create_project(
    session: AsyncSession, to_create: schemas.ProjectCreate
) -> models.Project:
    project = models.Project(
        **to_create.model_dump(),
    )
    if await queries.get_project_by_english_name(session, to_create.name.en):
        raise errors.SeisLabDataError(
            f"Project with english name {to_create.name.en!r} already exists."
        )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return await queries.get_project(session, to_create.id)


async def delete_project(
    session: AsyncSession,
    project_id: schemas.ProjectId,
) -> None:
    if project := (await queries.get_project(session, project_id)):
        await session.delete(project)
        await session.commit()
    else:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")


async def update_project(
    session: AsyncSession,
    project: models.Project,
    to_update: schemas.ProjectUpdate,
) -> models.Project:
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project
