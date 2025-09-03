from slugify import slugify
from sqlmodel.ext.asyncio.session import AsyncSession

from ... import (
    errors,
    schemas,
)
from .. import (
    models,
    queries,
)


async def create_project(
    session: AsyncSession, to_create: schemas.ProjectCreate
) -> models.Project:
    project = models.Project(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


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
        if key == "name":
            setattr(project, "slug", slugify(value.get("en", "")))
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project
