import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    errors,
    events,
)
from ..db import (
    commands,
    queries,
    models,
)
from .. import (
    permissions,
    schemas,
)

logger = logging.getLogger(__name__)


async def create_project(
    to_create: schemas.ProjectCreate,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> models.Project:
    if initiator is None or not await permissions.can_create_project(
        initiator, settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a marine campaign."
        )
    project = await commands.create_project(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.PROJECT_CREATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                after=schemas.ProjectReadDetail(**project.model_dump()).model_dump()
            ),
        )
    )
    return project


async def update_project(
    project_id: schemas.ProjectId,
    to_update: schemas.ProjectUpdate,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
):
    if initiator is None or not await permissions.can_update_project(
        initiator, project_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to update project.")
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")
    serialized_project_before = schemas.ProjectReadDetail.from_db_instance(
        project
    ).model_dump()
    updated_project = await commands.update_project(session, project, to_update)

    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.PROJECT_UPDATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                before=serialized_project_before,
                after=schemas.ProjectReadDetail.from_db_instance(
                    updated_project
                ).model_dump(),
            ),
        )
    )
    return updated_project


async def delete_project(
    project_id: schemas.ProjectId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_project(
        initiator, project_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to delete projects.")
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(f"Project with id {project_id} does not exist.")
    serialized_project = schemas.ProjectReadDetail(**project.model_dump()).model_dump()
    await commands.delete_project(session, project_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.PROJECT_DELETED,
            initiator=initiator.id,
            payload=schemas.EventPayload(before=serialized_project),
        )
    )


async def list_projects(
    session: AsyncSession,
    initiator: schemas.UserId | None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
) -> tuple[list[models.Project], int | None]:
    return await queries.paginated_list_projects(
        session, initiator, page, page_size, include_total
    )


async def get_project(
    project_id: schemas.ProjectId,
    initiator: schemas.User | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> models.Project | None:
    if not await permissions.can_read_project(initiator, project_id, settings=settings):
        raise errors.SeisLabDataError(
            f"User is not allowed to read project {project_id!r}."
        )
    return await queries.get_project(session, project_id)
