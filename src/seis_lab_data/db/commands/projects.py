import logging

from sqlalchemy import (
    func,
    select,
    update,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...constants import (
    PROJECT_IDLE_STATUSES,
    SURVEY_MISSION_IDLE_STATUSES,
    SURVEY_RELATED_RECORD_IDLE_STATUSES,
    ProjectStatus,
)
from ...schemas import identifiers
from ...schemas import projects as project_schemas
from .. import models
from ..queries import projects as project_queries
from . import common

logger = logging.getLogger(__name__)


async def create_project(
    session: AsyncSession, to_create: project_schemas.ProjectCreate
) -> models.Project:
    project = models.Project(
        **to_create.model_dump(
            exclude={"bbox_4326"},
            exclude_none=True,
        ),
        bbox_4326=(
            common.get_bbox_4326_for_db(bbox)
            if (bbox := to_create.bbox_4326) is not None
            else bbox
        ),
    )
    if await project_queries.get_project_by_name(session, to_create.name) is not None:
        raise errors.DuplicateResourceError(
            errors.N_("There is already a project named “%(name)s”."),
            name=to_create.name,
        )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return await project_queries.get_project(session, to_create.id)


async def delete_project(
    session: AsyncSession,
    project_id: identifiers.ProjectId,
) -> None:
    """Delete an idle project, along with its missions and their records.

    The project, its missions and their records are locked before their statuses
    are checked, so that no task can make any of them busy while the deletion runs:
    a task trying to do so waits for the deletion to end, and then finds nothing to
    change. Raises `SeisLabDataError` if the project does not exist, is busy or has
    busy missions or records.
    """
    project_status = await session.scalar(
        select(models.Project.status)
        .where(models.Project.id == project_id)
        .with_for_update()
    )
    if project_status is None:
        await session.rollback()
        raise errors.SeisLabDataError(
            errors.N_("Project %(id)s does not exist."), id=str(project_id)
        )
    if project_status not in PROJECT_IDLE_STATUSES:
        await session.rollback()
        raise errors.SeisLabDataError(
            errors.N_("Cannot delete the project because its status is %(status)s."),
            status=project_status.value,
        )
    # every mission and record is locked, as a busy one is told apart only once it
    # is locked: the statuses are counted with a filter rather than a WHERE clause,
    # which would be applied before the rows are locked
    locked_missions = (
        select(models.SurveyMission.status)
        .where(models.SurveyMission.project_id == project_id)
        .with_for_update()
        .subquery()
    )
    num_busy_missions = await session.scalar(
        select(
            func.count().filter(
                locked_missions.c.status.not_in(SURVEY_MISSION_IDLE_STATUSES)
            )
        ).select_from(locked_missions)
    )
    locked_records = (
        select(models.SurveyRelatedRecord.status)
        .join(models.SurveyMission)
        .where(models.SurveyMission.project_id == project_id)
        .with_for_update(of=models.SurveyRelatedRecord)
        .subquery()
    )
    num_busy_records = await session.scalar(
        select(
            func.count().filter(
                locked_records.c.status.not_in(SURVEY_RELATED_RECORD_IDLE_STATUSES)
            )
        ).select_from(locked_records)
    )
    if num_busy_missions > 0 or num_busy_records > 0:
        await session.rollback()
        raise errors.SeisLabDataError(
            errors.N_(
                "Cannot delete the project because some of its survey missions or survey-related records are currently being processed."
            )
        )
    await session.delete(await project_queries.get_project(session, project_id))
    await session.commit()


async def update_project(
    session: AsyncSession,
    project: models.Project,
    to_update: project_schemas.ProjectUpdate,
) -> models.Project:
    if (
        "name" in to_update.model_fields_set
        and (
            namesake := await project_queries.get_project_by_name(
                session, to_update.name
            )
        )
        is not None
        and namesake.id != project.id
    ):
        raise errors.DuplicateResourceError(
            errors.N_("There is already a project named “%(name)s”."),
            name=to_update.name,
        )
    for key, value in to_update.model_dump(
        exclude={"bbox_4326"}, exclude_unset=True
    ).items():
        setattr(project, key, value)
    updated_bbox_4326 = (
        common.get_bbox_4326_for_db(bbox)
        if (bbox := to_update.bbox_4326) is not None
        else None
    )
    project.bbox_4326 = updated_bbox_4326
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def update_project_validation_result(
    session: AsyncSession,
    project: models.Project,
    validation_result: models.ValidationResult,
) -> models.Project:
    """Unconditionally sets the project's validation result."""
    project.validation_result = validation_result
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return await project_queries.get_project(session, identifiers.ProjectId(project.id))


async def set_project_status(
    session: AsyncSession, project_id: identifiers.ProjectId, status: ProjectStatus
) -> models.Project:
    """Unconditionally sets the project's status."""
    if (project := (await project_queries.get_project(session, project_id))) is None:
        raise errors.SeisLabDataError(
            errors.N_("Project %(id)s does not exist."), id=str(project_id)
        )
    project.status = status
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return await project_queries.get_project(session, identifiers.ProjectId(project_id))


async def set_project_thumbnail(
    session: AsyncSession,
    project_id: identifiers.ProjectId,
    thumbnail: bytes | None,
) -> bool:
    """Sets the project's thumbnail and nothing else.

    `update_project` is no use here, it also overwrites the bbox.
    Returns whether the project still exists.
    """
    result = await session.exec(
        update(models.Project)
        .where(models.Project.id == project_id)
        .values(thumbnail=thumbnail)
    )
    await session.commit()
    return result.rowcount == 1
