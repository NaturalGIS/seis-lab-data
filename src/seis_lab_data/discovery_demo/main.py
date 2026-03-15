import json
import logging
import uuid

from anyio import Path

from ..db import models
from ..db.queries import recordassets as asset_queries
from ..operations import surveyrelatedrecords as survey_related_record_ops
from ..schemas import (
    discovery as discovery_schemas,
    surveyrelatedrecords as record_schemas,
    surveymissions as mission_schemas,
)
from ..schemas.common import (
    ProjectId,
    RecordAssetId,
    SurveyMissionId,
    UserId,
)

from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


async def discover_project_contents(
    session: AsyncSession,
    project: models.Project,
):
    """Discover project contents by looking for configured survey missions, records and assets"""
    # this would be pulled from DB, as one of the project properties instead
    # of being gotten from a file
    project_config = await _get_project_discovery_config(
        Path(__file__).parents[3] / "tests/data/project-discovery-base.json"
    )
    # - create survey missions
    missions_to_create = []
    for survey_mission_conf in project_config.survey_missions:
        missions_to_create.append(
            mission_schemas.SurveyMissionCreate(
                id=SurveyMissionId(uuid.uuid4()),
                owner=UserId(project.owner),
                project_id=ProjectId(project.id),
                name=survey_mission_conf.name,
                description=survey_mission_conf.description,
                relative_path=survey_mission_conf.discovery_pattern,
            )
        )
    # - discover each survey mission's contents


async def discover_survey_mission_contents(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
) -> None:
    record_discovery_configs = _get_project_discovery_config(
        Path(__file__).parents[3] / "tests/data/project-discovery-base.json"
    )
    records_to_create = []
    for idx, record_config in enumerate(record_discovery_configs):
        logger.debug(
            f"[{idx + 1}/{len(record_discovery_configs)}] Discovering record config {record_config.name!r}..."
        )
        if (
            to_create := await discover_record(session, record_config, survey_mission)
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
