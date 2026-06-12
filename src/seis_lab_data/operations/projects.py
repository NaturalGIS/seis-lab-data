import logging

import pydantic
import shapely
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    dispatch,
    errors,
    permissions,
    schemas,
)
from ..constants import ROLE_ADMIN, ROLE_SYSTEM_ADMIN, ProjectStatus
from ..db import (
    commands,
    queries,
    models,
)
from ..schemas import (
    events as event_schemas,
    identifiers,
)

logger = logging.getLogger(__name__)


async def create_project(
    to_create: schemas.ProjectCreate,
    initiator: schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.Project:
    if not permissions.can_create_project(initiator):
        raise errors.SeisLabDataError("User is not allowed to create a project.")
    project = await commands.create_project(session, to_create)
    await event_dispatcher(
        event_schemas.ProjectCreatedEvent(
            project_id=identifiers.ProjectId(project.id),
            initiator=initiator.id,
        )
    )
    return project


async def change_project_status(
    target_status: ProjectStatus,
    project_id: identifiers.ProjectId,
    initiator: schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.Project:
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")
    if not permissions.can_change_project_status(initiator, project):
        raise errors.SeisLabDataError("User is not allowed to change project status.")
    if (old_status := project.status) == target_status:
        logger.info(f"Project status is already set to {target_status} - nothing to do")
        return project
    updated_project = await commands.set_project_status(
        session, identifiers.ProjectId(project.id), target_status
    )
    await event_dispatcher(
        event_schemas.ProjectStatusChangedEvent(
            project_id=project_id,
            old_status=old_status,
            new_status=updated_project.status,
            initiator=initiator.id,
        )
    )
    return updated_project


async def validate_project(
    project_id: identifiers.ProjectId,
    initiator: schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.Project:
    await change_project_status(
        ProjectStatus.UNDER_VALIDATION, project_id, initiator, session, event_dispatcher
    )
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")
    if not permissions.can_validate_project(initiator, project):
        raise errors.SeisLabDataError("User is not allowed to validate project.")
    validation_errors = []
    try:
        schemas.ValidProject(**project.model_dump())
    except pydantic.ValidationError as err:
        for error in err.errors():
            validation_errors.append(
                {
                    "name": ".".join(str(i) for i in error["loc"]),
                    "message": error["msg"],
                    "type_": error["type"],
                }
            )
        await commands.update_project_validation_result(
            session,
            project,
            validation_result={
                "is_valid": False,
                "errors": validation_errors,
            },
        )
    else:
        await commands.update_project_validation_result(
            session, project, validation_result={"is_valid": True, "errors": None}
        )
    await event_dispatcher(
        event_schemas.ProjectValidatedEvent(
            project_id=project_id,
            is_valid=not validation_errors,
            initiator=initiator.id,
        )
    )
    await change_project_status(
        ProjectStatus.DRAFT, project_id, initiator, session, event_dispatcher
    )
    return project


async def update_project(
    project_id: identifiers.ProjectId,
    to_update: schemas.ProjectUpdate,
    initiator: schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.Project:
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")
    if not permissions.can_update_project(initiator, project):
        raise errors.SeisLabDataError("User is not allowed to update project.")
    if project.status != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot update project with status {project.status}."
        )
    updated_project = await commands.update_project(session, project, to_update)
    await event_dispatcher(
        event_schemas.ProjectUpdatedEvent(
            project_id=project_id,
            initiator=initiator.id,
        )
    )
    return updated_project


async def delete_project(
    project_id: identifiers.ProjectId,
    initiator: schemas.User | None,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")
    if not permissions.can_delete_project(initiator, project):
        raise errors.SeisLabDataError("User is not allowed to delete projects.")
    if project.status != ProjectStatus.DRAFT:
        raise errors.SeisLabDataError(
            f"Cannot delete project with status {project.status}."
        )
    await commands.delete_project(session, project_id)
    await event_dispatcher(
        event_schemas.ProjectDeletedEvent(
            project_id=project_id,
            initiator=initiator.id,
        )
    )


async def list_projects(
    session: AsyncSession,
    initiator: schemas.User | None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name_filter: str | None = None,
    pt_name_filter: str | None = None,
    spatial_intersect: shapely.Polygon | None = None,
    temporal_extent: schemas.TemporalExtentFilterValue | None = None,
) -> tuple[list[models.Project], int | None]:
    kwargs = dict(
        page=page,
        page_size=page_size,
        include_total=include_total,
        en_name_filter=en_name_filter,
        pt_name_filter=pt_name_filter,
        spatial_intersect=spatial_intersect,
        temporal_extent=temporal_extent,
    )
    if initiator is None:
        return await queries.list_published_projects(session, **kwargs)
    elif not {ROLE_ADMIN, ROLE_SYSTEM_ADMIN}.isdisjoint(initiator.roles):
        return await queries.list_projects(session, **kwargs)
    else:
        return await queries.list_accessible_projects(session, initiator.id, **kwargs)


async def get_project(
    project_id: identifiers.ProjectId,
    initiator: schemas.User | None,
    session: AsyncSession,
) -> models.Project | None:
    project = await queries.get_project(session, project_id)
    if project is None:
        return None
    if not permissions.can_read_project(initiator, project):
        raise errors.SeisLabDataError(
            f"User is not allowed to read project {project_id!r}."
        )
    return project
