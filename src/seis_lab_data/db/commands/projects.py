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
from .common import get_bbox_4326_for_db

logger = logging.getLogger(__name__)


async def create_project(
    session: AsyncSession, to_create: schemas.ProjectCreate
) -> models.Project:
    project = models.Project(
        **to_create.model_dump(exclude={"bbox_4326"}),
        bbox_4326=(
            get_bbox_4326_for_db(bbox)
            if (bbox := to_create.bbox_4326) is not None
            else bbox
        ),
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
    for key, value in to_update.model_dump(
        exclude={"bbox_4326"}, exclude_unset=True
    ).items():
        setattr(project, key, value)
    updated_bbox_4326 = (
        get_bbox_4326_for_db(bbox)
        if (bbox := to_update.bbox_4326) is not None
        else None
    )
    project.bbox_4326 = updated_bbox_4326
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project
