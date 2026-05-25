import json
import logging
import uuid

from anyio import Path

from ..db import models
from ..db.queries import surveymissions as survey_mission_queries
from ..db.queries import recordassets as asset_queries
from ..events import EventEmitterProtocol
from ..operations import (
    surveyrelatedrecords as survey_related_record_ops,
    surveymissions as survey_mission_ops,
)
from ..schemas import (
    LocalizableDraftName,
    LocalizableDraftDescription,
    ProjectDiscoveryConfiguration,
    ProjectId,
    RecordAssetCreate,
    RecordAssetDiscoveryConfiguration,
    RecordAssetId,
    RecordRelationDiscoveryConfiguration,
    SurveyMissionCreate,
    SurveyMissionId,
    SurveyMissionDiscoveryConfiguration,
    SurveyRecordDiscoveryConfiguration,
    SurveyRelatedRecordCreate,
    User,
    UserId,
)
from . import protocols

from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


async def _discover_survey_mission(
    session: AsyncSession,
    project: models.Project,
    survey_mission_discovery_conf: SurveyMissionDiscoveryConfiguration,
    owner: User | None = None,
) -> SurveyMissionCreate | None:
    mission_path = Path(
        "/".join(
            (
                project.root_path.rstrip("/"),
                survey_mission_discovery_conf.relative_path.lstrip("/"),
            )
        )
    )
    if not await mission_path.is_dir():
        return None
    project_id = ProjectId(project.id)
    if (
        existing_survey_mission
        := await survey_mission_queries.get_survey_mission_by_path(
            session, project_id, survey_mission_discovery_conf.relative_path
        )
    ) is not None:
        logger.debug(
            f"Found an already existing survey mission with the same "
            f"path ({existing_survey_mission.id!r}), skipping..."
        )
        return None
    return SurveyMissionCreate(  # noqa
        id=SurveyMissionId(uuid.uuid4()),
        owner_id=UserId(owner.id if owner else project.owner_id),
        project_id=project_id,
        name=LocalizableDraftName(**survey_mission_discovery_conf.name),
        description=LocalizableDraftDescription(
            **(survey_mission_discovery_conf.description or {})
        ),
        relative_path=survey_mission_discovery_conf.relative_path,
    )


async def _get_project_config(project: models.Project) -> ProjectDiscoveryConfiguration:
    """Temporary helper to retrieve sample project discovery config.

    This would be pulled from DB, as one of the project properties instead.
    """
    # of being gotten from a file
    discovery_config_path = (
        Path(__file__).parents[3] / "tests/data/project-discovery-base.json"
    )
    raw_conf = json.loads(await discovery_config_path.read_text())
    return ProjectDiscoveryConfiguration.from_raw_config(raw_conf)


async def discover_project_survey_missions(
    session: AsyncSession,
    project: models.Project,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
) -> list[tuple[models.SurveyMission, SurveyMissionDiscoveryConfiguration]]:
    """Discover a project's survey missions by scanning the filesystem.

    Discovered resources become owned by the input user, if provided.
    Otherwise, they become owned by the project owner.
    """
    project_config = await _get_project_config(project)
    created = []
    for survey_mission_discovery_conf in project_config.survey_missions:
        if (
            mission_to_create := await _discover_survey_mission(
                session, project, survey_mission_discovery_conf
            )
        ) is None:
            continue
        db_survey_mission = await survey_mission_ops.create_survey_mission(
            to_create=mission_to_create,
            initiator=user,
            session=session,
            event_emitter=event_emitter,
        )
        created.append((db_survey_mission, survey_mission_discovery_conf))
    return created


async def discover_project_contents(
    session: AsyncSession,
    project: models.Project,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
):
    # discover survey missions
    # for each discovered mission, discover its contents
    new_survey_missions = await discover_project_survey_missions(
        session, project, event_emitter, user
    )
    for survey_mission in new_survey_missions:
        await discover_survey_mission_records(
            session, survey_mission, event_emitter, user
        )


async def discover_survey_mission_records(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    survey_mission_discovery_conf: SurveyMissionDiscoveryConfiguration,
    records_discovery_conf: list[SurveyRecordDiscoveryConfiguration],
    record_relations_discovery_conf: list[RecordRelationDiscoveryConfiguration],
) -> None:
    records_to_create = []
    relationships_to_create = []  # noqa
    for idx, record_discovery_conf in enumerate(survey_mission_discovery_conf.records):
        logger.debug(
            f"[{idx + 1}/{len(survey_mission_discovery_conf.records)}] Discovering record "
            f"config {record_discovery_conf.name!r}..."
        )
        if (
            to_create := await discover_record(
                session, record_discovery_conf, survey_mission
            )
        ) is not None:
            records_to_create.append(to_create)
    await survey_related_record_ops.bulk_create_survey_records(
        session, records_to_create
    )


async def discover_record(
    session: AsyncSession,
    record_discovery_config: SurveyRecordDiscoveryConfiguration,
    survey_mission: models.SurveyMission,
) -> SurveyRelatedRecordCreate | None:
    base_path = Path(
        "/".join((survey_mission.project.root_path, survey_mission.relative_path))
    )
    discovered: list[protocols.DiscoveredAsset] = []
    for asset_conf in record_discovery_config.assets:
        if (
            found := await discover_asset(
                session, asset_conf, record_discovery_config, base_path
            )
        ) is None:
            logger.debug(f"Unable to locate new asset {asset_conf.name!r}")
            continue
        discovered.append(found)
    if not discovered:
        logger.warning(
            f"Unable to locate any new asset for record "
            f"configuration {record_discovery_config.name!r}"
        )
        return None
    return await protocols.extractor1(
        survey_mission=survey_mission,
        record_configuration=record_discovery_config,
        discovered_assets=discovered,
        session=session,
    )


async def discover_asset(
    session: AsyncSession,
    asset_conf: RecordAssetDiscoveryConfiguration,
    record_conf: SurveyRecordDiscoveryConfiguration,
    base_path: Path,
    survey_mission_conf: SurveyMissionDiscoveryConfiguration | None = None,
    project_conf: ProjectDiscoveryConfiguration | None = None,
) -> protocols.DiscoveredAsset | None:
    for discovery_pattern in asset_conf.discovery_patterns:
        to_look_for = discovery_pattern.format(
            dataset_category=record_conf.dataset_category,
            domain_type=record_conf.domain_type,
            workflow_stage=record_conf.workflow_stage,
            **(project_conf.extra_context if project_conf else {}),
            **(survey_mission_conf.extra_context if survey_mission_conf else {}),
            **record_conf.extra_context,
            **asset_conf.extra_context,
        )
        async for found_file_path in base_path.glob(to_look_for):
            relative_path = str(found_file_path.relative_to(base_path))
            asset_for_path = await asset_queries.get_record_asset_by_file_path(
                session, relative_path
            )
            if asset_for_path is not None:
                logger.debug(
                    f"path {found_file_path!r} is already in the catalog, skipping..."
                )
                continue
            asset = RecordAssetCreate(
                id=RecordAssetId(uuid.uuid4()),
                name=LocalizableDraftName(**asset_conf.name),
                description=(
                    LocalizableDraftDescription(**asset_conf.description)
                    if asset_conf.description
                    else LocalizableDraftDescription()
                ),
                relative_path=relative_path,
                links=list(asset_conf.links),
            )
            return asset, found_file_path
        else:
            logger.debug(
                f"Unable to locate any new file path for pattern {to_look_for!r}"
            )
    else:
        logger.debug(
            f"Unable to locate any new file path for asset {asset_conf.name!r}"
        )
    return None


async def discover_records():
    ...
    # for each record, form the context
    # then build al list of all possible combinations - those are sure to originate individual records
    # then try to find files that match each context combination, according to configured assets
    # capture the dynamic part(s) of each found file


async def _get_project_discovery_config(
    discovery_config_path: Path,
) -> ProjectDiscoveryConfiguration:
    raw_conf = json.loads(await discovery_config_path.read_text())
    return ProjectDiscoveryConfiguration.from_raw_config(raw_conf)
