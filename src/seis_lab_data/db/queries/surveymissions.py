from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ... import schemas
from ...db import models
from .common import _get_total_num_records


async def paginated_list_survey_missions(
    session: AsyncSession,
    user: schemas.User | None = None,
    project_id: schemas.ProjectId | None = None,
    page: int = 1,
    page_size: int = 20,
    include_total: bool = False,
    en_name: str | None = None,
    pt_name: str | None = None,
) -> tuple[list[models.SurveyMission], int | None]:
    limit = page_size
    offset = limit * (page - 1)
    return await list_survey_missions(
        session,
        user,
        project_id,
        limit,
        offset,
        include_total,
        en_name=en_name,
        pt_name=pt_name,
    )


async def list_survey_missions(
    session: AsyncSession,
    user: schemas.User | None = None,
    project_id: schemas.ProjectId | None = None,
    limit: int = 20,
    offset: int = 0,
    include_total: bool = False,
    en_name: str | None = None,
    pt_name: str | None = None,
) -> tuple[list[models.SurveyMission], int | None]:
    statement = select(models.SurveyMission).options(
        selectinload(models.SurveyMission.project)
    )
    if en_name:
        statement = statement.where(
            models.SurveyMission.name["en"].astext.ilike(f"%{en_name}%")
        )
    if pt_name:
        statement = statement.where(
            models.SurveyMission.name["pt"].astext.ilike(f"%{pt_name}%")
        )
    if project_id is not None:
        statement = statement.where(models.SurveyMission.project_id == project_id)
    items = (await session.exec(statement.offset(offset).limit(limit))).all()
    num_total = (
        await _get_total_num_records(session, statement) if include_total else None
    )
    return items, num_total


async def get_survey_mission(
    session: AsyncSession,
    survey_mission_id: schemas.SurveyMissionId,
) -> models.SurveyMission | None:
    statement = (
        select(models.SurveyMission)
        .where(models.SurveyMission.id == survey_mission_id)
        .options(selectinload(models.SurveyMission.project))
    )
    return (await session.exec(statement)).first()


async def get_survey_mission_by_english_name(
    session: AsyncSession,
    project_id: schemas.ProjectId,
    english_name: str,
) -> models.SurveyMission | None:
    statement = (
        select(models.SurveyMission)
        .where(models.SurveyMission.name["en"].astext == english_name)
        .where(models.SurveyMission.project_id == project_id)
        .options(selectinload(models.SurveyMission.project))
    )
    return (await session.exec(statement)).first()
