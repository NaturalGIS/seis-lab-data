import uuid

from slugify import slugify
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    errors,
    schemas,
)
from . import (
    models,
    queries,
)


async def create_dataset_category(
    session: AsyncSession,
    to_create: schemas.DatasetCategoryCreate,
) -> models.DatasetCategory:
    category = models.DatasetCategory(
        **to_create.model_dump(),
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def delete_dataset_category(
    session: AsyncSession,
    dataset_category_id: uuid.UUID,
) -> None:
    if dataset_category := (
        await queries.get_dataset_category(session, dataset_category_id)
    ):
        await session.delete(dataset_category)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Dataset category with id {dataset_category_id} does not exist."
        )


async def create_domain_type(
    session: AsyncSession,
    to_create: schemas.DomainTypeCreate,
) -> models.DomainType:
    domain_type = models.DomainType(
        **to_create.model_dump(),
    )
    session.add(domain_type)
    await session.commit()
    await session.refresh(domain_type)
    return domain_type


async def delete_domain_type(
    session: AsyncSession,
    domain_type_id: uuid.UUID,
) -> None:
    if domain_type := (await queries.get_domain_type(session, domain_type_id)):
        await session.delete(domain_type)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Domain type with id {domain_type_id} does not exist."
        )


async def create_workflow_stage(
    session: AsyncSession,
    to_create: schemas.WorkflowStageCreate,
) -> models.WorkflowStage:
    workflow_stage = models.WorkflowStage(
        **to_create.model_dump(),
    )
    session.add(workflow_stage)
    await session.commit()
    await session.refresh(workflow_stage)
    return workflow_stage


async def delete_workflow_stage(
    session: AsyncSession,
    workflow_stage_id: uuid.UUID,
) -> None:
    if workflow_stage := (await queries.get_workflow_stage(session, workflow_stage_id)):
        await session.delete(workflow_stage)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Workflow stage with id {workflow_stage_id} does not exist."
        )


async def create_marine_campaign(
    session: AsyncSession, to_create: schemas.MarineCampaignCreate
) -> models.MarineCampaign:
    campaign = models.MarineCampaign(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def delete_marine_campaign(
    session: AsyncSession,
    marine_campaign_id: uuid.UUID,
) -> None:
    if marine_campaign := (
        await queries.get_marine_campaign(session, marine_campaign_id)
    ):
        await session.delete(marine_campaign)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Marine campaign with id {marine_campaign_id} does not exist."
        )


async def update_marine_campaign(
    session: AsyncSession,
    campaign: models.MarineCampaign,
    to_update: schemas.MarineCampaignUpdate,
) -> models.MarineCampaign:
    for key, value in to_update.model_dump(exclude_unset=True).items():
        setattr(campaign, key, value)
        if key == "name":
            setattr(campaign, "slug", slugify(value.get("en", "")))
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def create_survey_mission(
    session: AsyncSession,
    to_create: schemas.SurveyMissionCreate,
) -> models.SurveyMission:
    survey_mission = models.SurveyMission(
        **to_create.model_dump(), slug=slugify(to_create.name.get("en", ""))
    )
    session.add(survey_mission)
    await session.commit()
    await session.refresh(survey_mission)
    return survey_mission
