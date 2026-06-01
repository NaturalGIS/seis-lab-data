import json
import logging
import re
import uuid
from collections.abc import AsyncIterator

from anyio import Path

from ..db import models
from ..db.queries import surveymissions as survey_mission_queries
from ..db.queries import recordassets as asset_queries
from ..events import EventEmitterProtocol
from ..operations import surveymissions as survey_mission_ops
from ..schemas import discovery as discovery_schemas
from ..schemas import (
    LocalizableDraftName,
    LocalizableDraftDescription,
    ProjectDiscoveryConfiguration,
    ProjectId,
    RecordAssetCreate,
    RecordAssetId,
    SurveyMissionCreate,
    SurveyMissionId,
    SurveyRelatedRecordCreate,
    User,
    UserId,
)

from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


async def discover_project_contents(
    session: AsyncSession,
    project: models.Project,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
):
    """Discover a new project's contents.

    This follows roughly a workflow like:
    - discover survey missions and save them in the db
    - for each survey mission, discover its records
    """
    new_survey_missions = await discover_project_survey_missions(
        session, project, event_emitter, user
    )
    for db_survey_mission in new_survey_missions:
        await discover_survey_mission_records(
            session, db_survey_mission, event_emitter, user
        )


async def discover_project_survey_missions(
    session: AsyncSession,
    project: models.Project,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
) -> list[models.SurveyMission]:
    """Discover and save a project's survey missions.

    Survey missions become owned by the input user, if provided. Otherwise, they
    are owned by the project owner.

    Note that this function does not discover whatever resources may be part of
    survey missions, it just creates the missions.
    """

    created = []
    for survey_mission_discovery_conf in project._discovery_config.survey_missions:
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
        created.append(db_survey_mission)
    return created


async def discover_survey_mission_records(
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
) -> None:
    if (
        mission_discovery_conf := _get_survey_mission_discovery_conf(survey_mission)
    ) is None:
        logger.warning(
            f"Could not determine survey mission discovery configuration for "
            f"mission {survey_mission.id!r}"
        )
        return None
    created_records = []
    relationships_to_create = []  # noqa
    for idx, record_discovery_conf_name in enumerate(
        mission_discovery_conf.record_configuration_ids
    ):
        logger.debug(
            f"[{idx + 1}/{len(mission_discovery_conf.record_configuration_ids)}] "
            f"Discovering record config {record_discovery_conf_name!r}..."
        )
        if (
            record_discovery_conf
            := survey_mission.project._discovery_config.records.get(
                record_discovery_conf_name
            )
        ) is None:
            logger.warning(
                f"Record conf named {record_discovery_conf_name!r} not found."
            )
            continue
        if (
            db_record := await discover_record(
                session, record_discovery_conf, survey_mission, event_emitter, user
            )
        ) is not None:
            created_records.append(db_record)
    # now we need to handle record relationships


async def discover_record(
    session: AsyncSession,
    record_discovery_config: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    survey_mission: models.SurveyMission,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
) -> SurveyRelatedRecordCreate | None:
    """Discover survey related records and their assets in the filesystem, and save them."""
    base_path = Path(
        "/".join((survey_mission.project.root_path, survey_mission.relative_path))
    )
    new_assets = []
    discovered_properties: dict[str, str] = {}
    for asset_conf in record_discovery_config.assets:
        if (
            discovered := discover_asset(
                session,
                asset_conf,
                record_discovery_config.extra_properties,
                base_path,
                discovered_properties,
            )
        ) is None:
            logger.debug(f"Unable to locate new asset {asset_conf.name!r}")
            continue
        new_asset, discovered_properties = discovered
        new_assets.append(new_asset)
    if len(new_assets) == 0:
        logger.warning(
            f"Unable to locate any new asset for record "
            f"configuration {record_discovery_config.name!r}"
        )
        return None
    return SurveyRelatedRecordCreate(
        id=None,
        owner_id=None,
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


async def _discover_survey_mission(
    session: AsyncSession,
    project: models.Project,
    survey_mission_discovery_conf: discovery_schemas.SurveyMissionDiscoveryConfiguration,
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


def _get_survey_mission_discovery_conf(
    survey_mission: models.SurveyMission,
) -> discovery_schemas.SurveyMissionDiscoveryConfiguration | None:
    """Find a mission's discovery configuration."""

    for discovery_conf in survey_mission.project._discovery_config.survey_missions:
        if discovery_conf.relative_path.lstrip(
            "/"
        ) == survey_mission.relative_path.lstrip("/"):
            return discovery_conf
    else:
        return None


async def discover_asset(
    session: AsyncSession,
    asset_conf: discovery_schemas.RecordAssetDiscoveryConfiguration,
    extra_properties: list[discovery_schemas.RecordProperty],
    base_path: Path,
    already_discovered_properties: dict[str, str],
) -> tuple[RecordAssetCreate, dict[str, str]] | None:
    for discovery_pattern in asset_conf.discovery_patterns:
        to_look_for = discovery_pattern.format(
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
            return RecordAssetCreate(
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
) -> ProjectDiscoveryConfiguration:
    raw_conf = json.loads(await discovery_config_path.read_text())
    return ProjectDiscoveryConfiguration.from_raw_config(raw_conf)


def _build_pattern_regex(
    template: str,
    properties: dict[str, discovery_schemas.RecordProperty],
) -> re.Pattern:
    def replacer(m: re.Match) -> str:
        name = m.group("prop_name")
        if name not in properties:
            raise ValueError(f"Placeholder {{{name}}} not found in extra_properties")
        return f"(?P<{name}>{properties[name].pattern})"

    regex_str = re.sub(r"\{(?P<prop_name>\w+)\}", replacer, template)
    return re.compile(regex_str)


async def discover_files(
    root: Path,
    config: discovery_schemas.RecordAssetDiscoveryConfiguration,
) -> AsyncIterator[discovery_schemas.DiscoveredFile]:
    compiled_patterns = [
        _build_pattern_regex(p, config.properties) for p in config.discovery_patterns
    ]

    async for path in root.rglob("*"):
        if not await path.is_file():
            continue

        relative = path.relative_to(root).as_posix()

        for pattern in compiled_patterns:
            m = pattern.search(relative)
            if not m:
                continue

            extracted = {}
            valid = True

            for name, prop in config.properties.items():
                try:
                    raw = m.group(name)
                except IndexError:
                    continue  # This placeholder isn't in this pattern — skip

                try:
                    value = prop.convert(raw)
                except Exception:
                    valid = False
                    break

                if not prop.validate_value(value):
                    valid = False
                    break

                extracted[name] = value

            if valid:
                yield discovery_schemas.DiscoveredFile(
                    path=str(path), properties=extracted
                )

            break  # matched a pattern, don't try others
