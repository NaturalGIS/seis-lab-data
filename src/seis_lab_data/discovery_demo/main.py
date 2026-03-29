import json
import logging
import uuid

from anyio import Path

from ..config import SeisLabDataSettings
from ..db import models
from ..db.queries import recordassets as asset_queries
from ..events import EventEmitterProtocol
from ..operations import (
    surveyrelatedrecords as survey_related_record_ops,
    surveymissions as survey_mission_ops,
)
from ..schemas import (
    discovery as discovery_schemas,
    surveyrelatedrecords as record_schemas,
    surveymissions as mission_schemas,
)
from ..schemas.common import (
    LocalizableDraftName,
    LocalizableDraftDescription,
    ProjectId,
    RecordAssetId,
    SurveyMissionId,
)
from ..schemas.user import User

from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


async def discover_project_contents(
    session: AsyncSession,
    project: models.Project,
    settings: SeisLabDataSettings,
    user: User,
    event_emitter: EventEmitterProtocol,
):
    """Discover project contents by looking for configured survey missions, records and assets"""
    # this would be pulled from DB, as one of the project properties instead
    # of being gotten from a file
    project_config = await _get_project_discovery_config(
        Path(__file__).parents[3] / "tests/data/project-discovery-base.json"
    )
    # first, create survey missions
    creation_map = {}
    for survey_mission_discovery_conf in project_config.survey_missions:
        relative_path = (
            patt[:-1]
            if (patt := survey_mission_discovery_conf.discovery_pattern).endswith("/")
            else patt
        )
        creation_map[
            survey_mission_discovery_conf
        ] = await survey_mission_ops.create_survey_mission(
            to_create=mission_schemas.SurveyMissionCreate(
                id=SurveyMissionId(uuid.uuid4()),
                owner=user.id,
                project_id=ProjectId(project.id),
                name=LocalizableDraftName(**survey_mission_discovery_conf.name),
                description=LocalizableDraftDescription(
                    **survey_mission_discovery_conf.description
                ),
                relative_path=relative_path,
            ),
            initiator=user,
            session=session,
            settings=settings,
            event_emitter=event_emitter,
        )
    # then discover each survey mission's contents


async def discover_survey_mission_contents(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    survey_mission_discovery_conf: discovery_schemas.SurveyMissionDiscoveryConfiguration,
    record_relations_discovery_conf: list[
        discovery_schemas.RecordRelationDiscoveryConfiguration
    ],
) -> None:
    records_to_create = []
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
    record_discovery_config: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    survey_mission: models.SurveyMission,
) -> record_schemas.SurveyRelatedRecordCreate | None:
    base_path = Path(
        "/".join((survey_mission.project.root_path, survey_mission.relative_path))
    )
    new_assets = []
    for asset_conf in record_discovery_config.assets:
        if (
            new_asset := discover_asset(
                session, asset_conf, record_discovery_config, base_path
            )
        ) is None:
            logger.debug(f"Unable to locate new asset {asset_conf.name!r}")
            continue
        new_assets.append(new_asset)
    if len(new_assets) == 0:
        logger.warning(
            f"Unable to locate any new asset for record "
            f"configuration {record_discovery_config.name!r}"
        )
        return None
    return record_schemas.SurveyRelatedRecordCreate(
        id=None,
        owner=None,
        survey_mission_id=None,
        name=None,
        description=None,
        dataset_category_id=None,
        domain_type_id=None,
        workflow_stage_id=None,
        relative_path=None,
        bbox_4326=None,
        temporal_extent_begin=None,
        temporal_extent_end=None,
        links=None,
        assets=new_assets,
        related_records=None,
    )


async def discover_asset(
    session: AsyncSession,
    asset_conf: discovery_schemas.RecordAssetDiscoveryConfiguration,
    record_conf: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    base_path: Path,
    survey_mission_conf: discovery_schemas.SurveyMissionDiscoveryConfiguration
    | None = None,
) -> record_schemas.RecordAssetCreate | None:
    for discovery_pattern in asset_conf.discovery_patterns:
        to_look_for = discovery_pattern.format(
            dataset_category=record_conf.dataset_category,
            domain_type=record_conf.domain_type,
            workflow_stage=record_conf.workflow_stage,
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
            return record_schemas.RecordAssetCreate(
                id=RecordAssetId(uuid.uuid4()),
                name=asset_conf.name,
                description=asset_conf.description,
                relative_path=relative_path,
                links=asset_conf.links,
            )
        else:
            logger.debug(
                f"Unable to locate any new file path for pattern {to_look_for!r}"
            )
    else:
        logger.debug(
            f"Unable to locate any new file path for asset {asset_conf.name!r}"
        )
    return None


async def _get_project_discovery_config(
    discovery_config_path: Path,
) -> discovery_schemas.ProjectDiscoveryConfiguration:
    raw_conf = json.loads(await discovery_config_path.read_text())
    return discovery_schemas.ProjectDiscoveryConfiguration.from_raw_config(raw_conf)
