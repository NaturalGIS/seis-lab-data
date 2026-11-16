import datetime as dt
import logging

from sqlalchemy import (
    Boolean,
    and_,
    case,
    cast,
    func,
    select,
    true,
    update,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...constants import (
    SURVEY_MISSION_DISCOVERY_STATUSES,
    SURVEY_MISSION_IDLE_STATUSES,
    SURVEY_RELATED_RECORD_IDLE_STATUSES,
    ProjectStatus,
    SurveyMissionStatus,
)
from ...schemas import identifiers
from ...schemas import surveymissions as mission_schemas
from .. import models
from ..queries import surveymissions as mission_queries
from .common import get_bbox_4326_for_db

logger = logging.getLogger(__name__)


async def create_survey_mission(
    session: AsyncSession,
    to_create: mission_schemas.SurveyMissionCreate,
) -> models.SurveyMission:
    survey_mission = models.SurveyMission(
        **to_create.model_dump(exclude={"bbox_4326"}),
        bbox_4326=(
            get_bbox_4326_for_db(bbox)
            if (bbox := to_create.bbox_4326) is not None
            else bbox
        ),
    )
    # need to ensure name is unique for combination of project and survey mission
    if await mission_queries.get_survey_mission_by_name(
        session, identifiers.ProjectId(to_create.project_id), to_create.name
    ):
        raise errors.DuplicateResourceError(
            errors.N_(
                "There is already a survey mission named “%(name)s” in the same project."
            ),
            name=to_create.name,
        )

    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return await mission_queries.get_survey_mission(session, to_create.id)


async def delete_survey_mission(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
) -> None:
    """Delete an idle survey mission, along with its records.

    The mission and its records are locked before their statuses are checked, so
    that no task can make any of them busy while the deletion runs: a task trying
    to do so waits for the deletion to end, and then finds nothing to change.
    Raises `SeisLabDataError` if the mission does not exist, is busy or has busy
    records.
    """
    mission_status = await session.scalar(
        select(models.SurveyMission.status)
        .where(models.SurveyMission.id == survey_mission_id)
        .with_for_update()
    )
    if mission_status is None:
        await session.rollback()
        raise errors.SeisLabDataError(
            errors.N_("Survey mission %(id)s does not exist."),
            id=str(survey_mission_id),
        )
    if mission_status not in SURVEY_MISSION_IDLE_STATUSES:
        await session.rollback()
        raise errors.SeisLabDataError(
            errors.N_(
                "Cannot delete the survey mission because its status is %(status)s."
            ),
            status=mission_status.value,
        )
    # every record is locked, as a busy one is told apart only once it is locked: the
    # statuses are counted with a filter rather than a WHERE clause, which would be
    # applied before the rows are locked
    locked_records = (
        select(models.SurveyRelatedRecord.status)
        .where(models.SurveyRelatedRecord.survey_mission_id == survey_mission_id)
        .with_for_update()
        .subquery()
    )
    num_busy_records = await session.scalar(
        select(
            func.count().filter(
                locked_records.c.status.not_in(SURVEY_RELATED_RECORD_IDLE_STATUSES)
            )
        ).select_from(locked_records)
    )
    if num_busy_records > 0:
        await session.rollback()
        raise errors.SeisLabDataError(
            errors.N_(
                "Cannot delete the survey mission because some of its survey-related records are currently being processed."
            )
        )
    await session.delete(
        await mission_queries.get_survey_mission(session, survey_mission_id)
    )
    await session.commit()


async def update_survey_mission(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    to_update: mission_schemas.SurveyMissionUpdate,
) -> models.SurveyMission:
    logger.debug(f"{to_update.model_dump()=}")
    for key, value in to_update.model_dump(
        exclude={"bbox_4326"}, exclude_unset=True
    ).items():
        setattr(survey_mission, key, value)
    updated_bbox_4326 = (
        get_bbox_4326_for_db(bbox)
        if (bbox := to_update.bbox_4326) is not None
        else None
    )
    survey_mission.bbox_4326 = updated_bbox_4326
    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return survey_mission


async def update_survey_mission_validation_result(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    validation_result: models.ValidationResult,
) -> models.SurveyMission:
    """Unconditionally sets the survey mission's validation result."""
    survey_mission.validation_result = validation_result
    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return await mission_queries.get_survey_mission(
        session, identifiers.SurveyMissionId(survey_mission.id)
    )


async def set_survey_mission_status(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
    status: SurveyMissionStatus,
) -> models.SurveyMission:
    """Unconditionally sets the survey mission's status."""
    if (
        survey_mission := (
            await mission_queries.get_survey_mission(session, survey_mission_id)
        )
    ) is None:
        raise errors.SeisLabDataError(
            errors.N_("Survey mission %(id)s does not exist."),
            id=str(survey_mission_id),
        )
    survey_mission.status = status
    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return await mission_queries.get_survey_mission(
        session, identifiers.SurveyMissionId(survey_mission_id)
    )


async def compare_and_set_survey_mission_status(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
    expected_status: SurveyMissionStatus,
    status: SurveyMissionStatus,
) -> bool:
    """Sets the survey mission's status, but only if it is the expected one.

    Comparison and change are a single UPDATE, so of several callers which
    expect the same status only one gets to change it. A change to cancelling
    discovery keeps `updated_at`, the discovery heartbeat, as it is: the request
    to cancel is not a sign of the discovery being alive, and refreshing the
    heartbeat would delay the recovery of a discovery whose worker died. Returns
    whether the status was changed.
    """
    values = {"status": status}
    if status == SurveyMissionStatus.CANCELLING_DISCOVERY:
        # an explicit value prevents the column's `onupdate`
        values["updated_at"] = models.SurveyMission.updated_at
    result = await session.exec(
        update(models.SurveyMission)
        .where(models.SurveyMission.id == survey_mission_id)
        .where(models.SurveyMission.status == expected_status)
        .values(**values)
    )
    await session.commit()
    return result.rowcount == 1


async def refresh_survey_mission_discovery_heartbeat(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
) -> SurveyMissionStatus | None:
    """Set the `updated_at` of a survey mission that is under discovery to now.

    Applies to survey missions whose status is either under discovery or
    cancelling discovery. Returns the survey mission's status, or None if the
    survey mission is not in one of those statuses.
    """
    result = await session.exec(
        update(models.SurveyMission)
        .where(models.SurveyMission.id == survey_mission_id)
        .where(
            models.SurveyMission.status.in_(
                (
                    SurveyMissionStatus.UNDER_DISCOVERY,
                    SurveyMissionStatus.CANCELLING_DISCOVERY,
                )
            )
        )
        .values(updated_at=func.now())
        .returning(models.SurveyMission.status)
    )
    await session.commit()
    return result.scalar_one_or_none()


def _build_survey_mission_idle_status():
    """Build the SQL expression of the status of a survey mission which is idle.

    An idle survey mission is published if it is valid and its project is
    published, otherwise it is a draft. This is the status which survey mission
    updates and the publication of projects give to a survey mission.
    """
    project_status = (
        select(models.Project.status)
        .where(models.Project.id == models.SurveyMission.project_id)
        .scalar_subquery()
    )
    # the enum values are bound as text, hence the cast to the column's enum type,
    # which stores the enum names
    return cast(
        case(
            (
                and_(
                    models.SurveyMission.validation_result["is_valid"].astext.cast(
                        Boolean
                    )
                    == true(),
                    project_status == ProjectStatus.PUBLISHED,
                ),
                SurveyMissionStatus.PUBLISHED.name,
            ),
            else_=SurveyMissionStatus.DRAFT.name,
        ),
        models.SurveyMission.status.type,
    )


async def end_survey_mission_discovery(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
) -> SurveyMissionStatus | None:
    """Set the status of a survey mission under discovery to its idle status.

    The idle status is published if the survey mission is valid and its project
    is published, and draft otherwise. The status held when the discovery started
    is not reused, as the project may have been published or unpublished during
    the discovery, which leaves survey missions under discovery untouched.
    Applies only to a survey mission whose status is either under discovery or
    cancelling discovery. Returns the new status, or None if the survey mission is
    not in one of those statuses.
    """
    result = await session.exec(
        update(models.SurveyMission)
        .where(models.SurveyMission.id == survey_mission_id)
        .where(models.SurveyMission.status.in_(SURVEY_MISSION_DISCOVERY_STATUSES))
        .values(status=_build_survey_mission_idle_status())
        .returning(models.SurveyMission.status)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def recover_stale_survey_mission_discoveries(
    session: AsyncSession,
    stale_after: dt.timedelta,
    survey_mission_id: identifiers.SurveyMissionId | None = None,
) -> list[tuple[identifiers.SurveyMissionId, str, SurveyMissionStatus]]:
    """Set the survey missions whose discovery heartbeat is stale to their idle status.

    A survey mission's discovery heartbeat is stale if its status is either under
    discovery or cancelling discovery and its `updated_at` is older than
    `stale_after`. The idle status is the same as in `end_survey_mission_discovery`.
    The update is restricted to a single survey mission if `survey_mission_id` is
    given. Returns the ids, names and new statuses of the recovered survey
    missions.
    """
    statement = (
        update(models.SurveyMission)
        .where(models.SurveyMission.status.in_(SURVEY_MISSION_DISCOVERY_STATUSES))
        .where(models.SurveyMission.updated_at < func.now() - stale_after)
        .values(status=_build_survey_mission_idle_status())
        .returning(
            models.SurveyMission.id,
            models.SurveyMission.name,
            models.SurveyMission.status,
        )
    )
    if survey_mission_id is not None:
        statement = statement.where(models.SurveyMission.id == survey_mission_id)
    result = await session.exec(statement)
    await session.commit()
    return [
        (identifiers.SurveyMissionId(id_), name, status)
        for id_, name, status in result.all()
    ]


async def set_survey_mission_thumbnail(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
    thumbnail: bytes | None,
) -> bool:
    """Sets the survey mission's thumbnail and nothing else.

    `update_survey_mission` is no use here, it also overwrites the bbox.
    Returns whether the survey mission still exists.
    """
    result = await session.exec(
        update(models.SurveyMission)
        .where(models.SurveyMission.id == survey_mission_id)
        .values(thumbnail=thumbnail)
    )
    await session.commit()
    return result.rowcount == 1


async def bulk_publish_valid_survey_missions_for_project(
    session: AsyncSession,
    project_id: identifiers.ProjectId,
) -> list[identifiers.SurveyMissionId]:
    """Publish every already-valid, not-yet-published mission of a project.

    A mission's own validity does not depend on its parent project, so when
    the project (re)becomes valid there is no need to re-validate its
    missions - those already marked valid can be published directly from
    their stored validation result. Returns the ids of the missions that
    got published, so callers can further cascade to those missions' own
    records.
    """
    result = await session.exec(
        update(models.SurveyMission)
        .where(models.SurveyMission.project_id == project_id)
        # missions in any other status are being worked on by a task
        .where(models.SurveyMission.status == SurveyMissionStatus.DRAFT)
        .where(
            models.SurveyMission.validation_result["is_valid"].astext.cast(Boolean)
            == true()
        )
        .values(status=SurveyMissionStatus.PUBLISHED)
        .returning(models.SurveyMission.id)
    )
    await session.commit()
    return [identifiers.SurveyMissionId(row) for row in result.scalars().all()]


async def bulk_unpublish_survey_missions_for_project(
    session: AsyncSession,
    project_id: identifiers.ProjectId,
) -> list[identifiers.SurveyMissionId]:
    """Unpublish every published mission of a project.

    Used when the project becomes invalid, so its missions don't stay
    published without a published parent. Returns the ids of the missions
    that got unpublished, so callers can further cascade to those missions'
    own records.
    """
    result = await session.exec(
        update(models.SurveyMission)
        .where(models.SurveyMission.project_id == project_id)
        .where(models.SurveyMission.status == SurveyMissionStatus.PUBLISHED)
        .values(status=SurveyMissionStatus.DRAFT)
        .returning(models.SurveyMission.id)
    )
    await session.commit()
    return [identifiers.SurveyMissionId(row) for row in result.scalars().all()]
