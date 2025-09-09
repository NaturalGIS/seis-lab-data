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
):
    if initiator is None or not await permissions.can_create_project(
        initiator, settings
    ):
        raise errors.SeisLabDataError(
            "User is not allowed to create a marine campaign."
        )
    campaign = await commands.create_project(session, to_create)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.PROJECT_CREATED,
            initiator=initiator.id,
            payload=schemas.EventPayload(
                after=schemas.ProjectReadDetail(**campaign.model_dump()).model_dump()
            ),
        )
    )
    return campaign


async def delete_project(
    project_id: schemas.ProjectId,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
    event_emitter: events.EventEmitterProtocol,
) -> None:
    if initiator is None or not await permissions.can_delete_project(
        initiator, project_id, settings=settings
    ):
        raise errors.SeisLabDataError("User is not allowed to delete marine campaigns.")
    if (project := await queries.get_project(session, project_id)) is None:
        raise errors.SeisLabDataError(
            f"Marine campaign with id {project_id} does not exist."
        )
    serialized_project = schemas.ProjectReadDetail(**project.model_dump()).model_dump()
    await commands.delete_project(session, project_id)
    event_emitter(
        schemas.SeisLabDataEvent(
            type_=schemas.EventType.PROJECT_DELETED,
            initiator=initiator,
            payload=schemas.EventPayload(before=serialized_project),
        )
    )


async def list_projects(
    session: AsyncSession,
    initiator: schemas.UserId | None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
) -> tuple[list[models.Project], int | None]:
    return await queries.list_projects(session, initiator, limit, offset, include_total)


async def get_project_by_slug(
    project_slug: str,
    initiator: schemas.UserId | None,
    session: AsyncSession,
    settings: config.SeisLabDataSettings,
) -> models.Project | None:
    if not permissions.can_read_project(initiator, project_slug, settings=settings):
        raise errors.SeisLabDataError(
            f"User is not allowed to read project {project_slug!r}."
        )
    return await queries.get_project_by_slug(session, project_slug)
