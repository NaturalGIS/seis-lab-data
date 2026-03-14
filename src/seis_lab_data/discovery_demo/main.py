import json
import logging
from pathlib import Path

from ..db import models
from ..schemas import discovery as discovery_schemas
from ..schemas import surveyrelatedrecords as record_schemas

logger = logging.getLogger(__name__)


def get_project_discovery_config(
    discovery_config_path: Path,
) -> list[discovery_schemas.SurveyRecordDiscoveryConfiguration]:
    raw_conf = json.loads(discovery_config_path.read_text())
    parsed_record_confs = []
    for record_conf_id, record_conf in raw_conf["records"].items():
        parsed_record_confs.append(
            discovery_schemas.SurveyRecordDiscoveryConfiguration.from_raw_config(
                record_conf_id,
                record_conf,
                raw_conf.get("record_relations"),
            )
        )
    return parsed_record_confs


def discover_record(
    record_discovery_config: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    survey_mission: models.SurveyMission,
) -> record_schemas.SurveyRelatedRecordCreate | None:
    for asset_conf in record_discovery_config.assets:
        for discovery_pattern in asset_conf.discovery_patterns:
            to_look_for = discovery_pattern.format(
                survey_mission_base_path="/".join(
                    (
                        survey_mission.project.root_path,
                        survey_mission.relative_path,
                    )
                ),
                dataset_category=record_discovery_config.dataset_category,
                domain_type=record_discovery_config.domain_type,
                workflow_stage=record_discovery_config.workflow_stage,
                **record_discovery_config.extra_context,
            )
            if not (asset_path := Path(to_look_for)).exists():
                logger.debug(f"Could not find {asset_path!r}")
                continue
            record_schemas.RecordAssetCreate(
                id=None,
                name=None,
                description=None,
                relative_path=None,
                links=None,
            )
