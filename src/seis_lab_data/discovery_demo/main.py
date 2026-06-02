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
        new_records = await discover_record(
            session, record_discovery_conf, survey_mission, event_emitter, user
        )
        created_records.extend(new_records)
    # now we need to handle record relationships


def _files_are_compatible(
    anchor: discovery_schemas.DiscoveredFile,
    candidate: discovery_schemas.DiscoveredFile,
    properties: list[discovery_schemas.RecordProperty],
) -> bool:
    """Return True if candidate is compatible with anchor for all shared properties.

    A property is only checked when both files extracted a value for it. The
    compatibility criterion is defined per property type (e.g. exact equality for
    constants, delta threshold for datetimes).
    """
    for prop in properties:
        a = anchor.properties.get(prop.identifier)
        b = candidate.properties.get(prop.identifier)
        if a is None or b is None:
            continue  # property absent in one file — no constraint
        if not prop.is_compatible(a, b):
            return False
    return True


async def scan_record_instances(
    base_path: Path,
    record_conf: discovery_schemas.SurveyRecordDiscoveryConfiguration,
) -> list[discovery_schemas.DiscoveredRecord]:
    """Scan the filesystem for all file groups matching a record config.

    Uses asset[0] files as anchors. For each anchor, searches the remaining
    asset lists for the first file that is compatible with the anchor across
    all shared properties. A record instance is formed only when every asset
    type yields a compatible file.
    """
    asset_files: list[list[discovery_schemas.DiscoveredFile]] = []
    for asset_conf in record_conf.assets:
        files = [f async for f in discover_files(base_path, asset_conf)]
        asset_files.append(files)

    if not asset_files or any(not files for files in asset_files):
        return []

    extra_props = record_conf.extra_properties or []
    results = []

    for anchor in asset_files[0]:
        instance_assets: dict[int, discovery_schemas.DiscoveredFile] = {0: anchor}
        complete = True
        for asset_idx in range(1, len(asset_files)):
            match = next(
                (
                    f
                    for f in asset_files[asset_idx]
                    if _files_are_compatible(anchor, f, extra_props)
                ),
                None,
            )
            if match is None:
                logger.debug(
                    f"No compatible file for asset {asset_idx} "
                    f"against anchor {anchor.path!r}"
                )
                complete = False
                break
            instance_assets[asset_idx] = match

        if complete:
            results.append(
                discovery_schemas.DiscoveredRecord(
                    properties={
                        prop.identifier: anchor.properties[prop.identifier]
                        for prop in extra_props
                        if prop.identifier in anchor.properties
                    },
                    assets=instance_assets,
                )
            )

    return results


async def discover_record(
    session: AsyncSession,
    record_discovery_config: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    survey_mission: models.SurveyMission,
    event_emitter: EventEmitterProtocol,
    user: User | None = None,
) -> list[SurveyRelatedRecordCreate]:
    """Discover survey-related record instances and their assets in the filesystem.

    Each returned item represents one record instance (a group of matched assets
    that share the same property values). Instances whose assets are already in
    the catalog are filtered out.
    """
    base_path = Path(
        "/".join(
            (
                survey_mission.project.root_path.rstrip("/"),
                survey_mission.relative_path.lstrip("/"),
            )
        )
    )
    if not (
        instances := await scan_record_instances(base_path, record_discovery_config)
    ):
        logger.warning(
            f"No record instances found for config {record_discovery_config.id_!r}"
        )
        return []

    results = []
    for instance in instances:
        instance_assets = []
        already_catalogued = False
        for asset_idx, discovered_file in instance.assets.items():
            asset_conf = record_discovery_config.assets[asset_idx]
            relative_path = str(Path(discovered_file.path).relative_to(base_path))
            if (
                await asset_queries.get_record_asset_by_file_path(
                    session, relative_path
                )
                is not None
            ):
                logger.debug(
                    f"path {relative_path!r} is already in the catalog, skipping instance"
                )
                already_catalogued = True
                break
            instance_assets.append(
                RecordAssetCreate(
                    id=RecordAssetId(uuid.uuid4()),
                    name=asset_conf.name,
                    description=asset_conf.description,
                    relative_path=relative_path,
                    links=asset_conf.links,
                )
            )
        if not already_catalogued and instance_assets:
            results.append(
                SurveyRelatedRecordCreate(
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
                    assets=instance_assets,
                    related_records=None,
                )
            )
    return results


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
