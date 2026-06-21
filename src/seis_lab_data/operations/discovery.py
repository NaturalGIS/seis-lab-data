import logging
import re
import uuid
from collections.abc import AsyncIterator

from anyio import Path
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    constants,
    errors,
    permissions,
)
from ..schemas import (
    common,
    events as event_schemas,
    discovery as discovery_schemas,
    identifiers,
    surveymissions as mission_schemas,
    surveyrelatedrecords as record_schemas,
    user as user_schemas,
)
from ..db import models
from ..db.queries import (
    projects as project_queries,
    surveymissions as survey_mission_queries,
    surveyrelatedrecords as record_queries,
    recordassets as asset_queries,
)
from .. import dispatch

from . import (
    projects as project_ops,
    surveymissions as survey_mission_ops,
    surveyrelatedrecords as record_ops,
)

logger = logging.getLogger(__name__)


def _get_survey_mission_discovery_conf(
    survey_mission: models.SurveyMission,
) -> discovery_schemas.SurveyMissionDiscoveryConfiguration | None:
    """Find a mission's discovery configuration."""

    project_discovery_conf = (
        discovery_schemas.ProjectDiscoveryConfiguration.from_raw_config(
            survey_mission.project.discovery_configuration
        )
    )
    for mission_discovery_conf in project_discovery_conf.survey_missions:
        if mission_discovery_conf.relative_path.strip(
            "/"
        ) == survey_mission.relative_path.strip("/"):
            return mission_discovery_conf
    else:
        return None


async def discover_survey_mission_records(
    *,
    request_id: identifiers.RequestId,
    session: AsyncSession,
    archive_root: str,
    survey_mission: models.SurveyMission,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    user: user_schemas.User,
) -> AsyncIterator[models.SurveyRelatedRecord]:
    if (
        mission_discovery_conf := _get_survey_mission_discovery_conf(survey_mission)
    ) is None:
        logger.warning(
            f"Could not determine survey mission discovery configuration for "
            f"mission {survey_mission.id!r}"
        )
        return

    project_discovery_conf = (
        discovery_schemas.ProjectDiscoveryConfiguration.from_raw_config(
            survey_mission.project.discovery_configuration
        )
        if survey_mission.project.discovery_configuration
        else None
    )
    if project_discovery_conf is None:
        logger.warning(
            "The survey mission's project does not have a discovery configuration - Cannot discover records"
        )
        return

    relationships_to_create = []  # noqa
    for idx, record_discovery_conf_name in enumerate(
        mission_discovery_conf.record_configuration_ids
    ):
        logger.debug(
            f"[{idx + 1}/{len(mission_discovery_conf.record_configuration_ids)}] "
            f"Discovering record config {record_discovery_conf_name!r}..."
        )
        if (
            record_discovery_conf := project_discovery_conf.records.get(
                record_discovery_conf_name
            )
        ) is None:
            logger.warning(
                f"Record conf named {record_discovery_conf_name!r} not found."
            )
            continue
        new_records = await discover_records(
            session=session,
            archive_root=archive_root,
            record_discovery_config=record_discovery_conf,
            survey_mission=survey_mission,
            owner_id=identifiers.UserId(user.id) if user else None,
        )
        for new_record in new_records:
            created_record = await record_ops.create_survey_related_record(
                request_id=request_id,
                to_create=new_record,
                initiator=user,
                session=session,
                event_dispatcher=event_dispatcher,
            )
            yield created_record
        # TODO: now we need to handle record relationships


async def discover_records(
    *,
    session: AsyncSession,
    archive_root: str,
    record_discovery_config: discovery_schemas.SurveyRecordDiscoveryConfiguration,
    survey_mission: models.SurveyMission,
    owner_id: identifiers.UserId | None = None,
) -> list[record_schemas.SurveyRelatedRecordCreate]:
    """Discover survey-related record instances and their assets in the filesystem.

    Each returned item represents one record instance (a group of matched assets
    that share the same property values). Instances whose assets are already in
    the catalog are filtered out.
    """
    if (
        dataset_category := await record_queries.get_dataset_category_by_english_name(
            session, record_discovery_config.dataset_category
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Unknown dataset category: {record_discovery_config.dataset_category!r}"
        )
    if (
        domain_type := await record_queries.get_domain_type_by_english_name(
            session, record_discovery_config.domain_type
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Unknown domain type: {record_discovery_config.domain_type!r}"
        )
    if (
        workflow_stage := await record_queries.get_workflow_stage_by_english_name(
            session, record_discovery_config.workflow_stage
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Unknown workflow stage: {record_discovery_config.workflow_stage!r}"
        )

    base_path = Path(
        "/".join(
            (
                archive_root,
                survey_mission.project.root_path.strip("/"),
                survey_mission.relative_path.strip("/"),
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
                record_schemas.RecordAssetCreate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name=asset_conf.name,
                    description=asset_conf.description or {},
                    relative_path=relative_path,
                    links=asset_conf.links,
                )
            )
        extra_props = {k: str(v) for k, v in instance.properties.items()}
        logger.debug(f"{extra_props=}")
        logger.debug(f"{record_discovery_config.name=}")
        da_name = {
            k: v.format(**extra_props) for k, v in record_discovery_config.name.items()
        }
        logger.debug(f"{da_name=}")
        if not already_catalogued and instance_assets:
            results.append(
                record_schemas.SurveyRelatedRecordCreate(
                    id=identifiers.SurveyRelatedRecordId(uuid.uuid4()),
                    owner_id=owner_id or identifiers.UserId(survey_mission.owner_id),
                    survey_mission_id=identifiers.SurveyMissionId(survey_mission.id),
                    name={
                        k: v.format(**extra_props)
                        for k, v in record_discovery_config.name.items()
                    },
                    description=record_discovery_config.description or {},
                    dataset_category_id=identifiers.DatasetCategoryId(
                        dataset_category.id
                    ),
                    domain_type_id=identifiers.DomainTypeId(domain_type.id),
                    workflow_stage_id=identifiers.WorkflowStageId(workflow_stage.id),
                    bbox_4326=None,
                    temporal_extent_begin=None,
                    temporal_extent_end=None,
                    links=[],
                    assets=instance_assets,
                    related_records=[],
                    extra_properties={
                        k: str(v) for k, v in instance.properties.items()
                    },
                ),
            )
    return results


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


async def discover_files(
    root: Path,
    asset_config: discovery_schemas.RecordAssetDiscoveryConfiguration,
) -> AsyncIterator[discovery_schemas.DiscoveredFile]:
    compiled_patterns = [
        _build_pattern_regex(p, asset_config.properties)
        for p in asset_config.discovery_patterns
    ]
    logger.debug(f"{root=}")
    for pat_idx, pattern in enumerate(compiled_patterns):
        last_dir, fname = pattern.pattern.rpartition("/")[::2]
        logger.debug(f"{last_dir=}")
        logger.debug(f"{fname=}")
        pattern_root = root / last_dir
        idx = 0
        async for path in pattern_root.rglob("*"):
            idx += 1
            if not await path.is_file():
                continue

            relative = path.relative_to(root).as_posix()
            logger.debug(f"{relative=}")
            logger.debug(f"{pattern.pattern=}")
            m = pattern.search(relative)
            if not m:
                continue
            logger.debug(f"Found file {relative=}")
            extracted = {
                "index": f"{pat_idx}_{idx}",
            }
            valid = True

            for name, prop in asset_config.properties.items():
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
                logger.debug(f"Yielding path {str(path)=} properties {extracted=}")
                yield discovery_schemas.DiscoveredFile(
                    path=str(path), properties=extracted
                )

            break  # matched a pattern, don't try others

    # async for path in root.rglob("*"):
    #     if not await path.is_file():
    #         continue
    #
    #     relative = path.relative_to(root).as_posix()
    #
    #     for pattern in compiled_patterns:
    #         m = pattern.search(relative)
    #         if not m:
    #             continue
    #
    #         logger.debug(f"Found file {relative=}")
    #
    #         extracted = {}
    #         valid = True
    #
    #         for name, prop in asset_config.properties.items():
    #             try:
    #                 raw = m.group(name)
    #             except IndexError:
    #                 continue  # This placeholder isn't in this pattern — skip
    #
    #             try:
    #                 value = prop.convert(raw)
    #             except Exception:
    #                 valid = False
    #                 break
    #
    #             if not prop.validate_value(value):
    #                 valid = False
    #                 break
    #
    #             extracted[name] = value
    #
    #         if valid:
    #             yield discovery_schemas.DiscoveredFile(
    #                 path=str(path), properties=extracted
    #             )
    #
    #         break  # matched a pattern, don't try others


def _build_pattern_regex(
    template: str,
    properties: dict[str, discovery_schemas.RecordProperty],
) -> re.Pattern:
    logger.debug(f"{properties=}")
    seen: set[str] = set()

    def replacer(m: re.Match) -> str:
        name = m.group("prop_name")
        if name not in properties:
            raise ValueError(f"Placeholder {name} not found in extra_properties")
        if name in seen:
            return f"(?P={name})"
        seen.add(name)
        return f"(?P<{name}>{properties[name].pattern})"

    regex_str = re.sub(r"\{\{(?P<prop_name>\w+)\}\}", replacer, template)
    logger.debug(f"{regex_str=}")
    return re.compile(regex_str)


async def discover_project_survey_missions(
    *,
    request_id: identifiers.RequestId,
    session: AsyncSession,
    project: models.Project,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
    user: user_schemas.User,
) -> AsyncIterator[models.SurveyMission | None]:
    """Discover and save a project's survey missions.

    Survey missions become owned by the input user, if provided. Otherwise, they
    are owned by the project owner.

    Note that this function does not discover whatever resources may be part of
    survey missions, it just creates the missions.
    """
    discovery_configuration = (
        discovery_schemas.ProjectDiscoveryConfiguration.model_validate(
            project.discovery_configuration
        )
    )
    for survey_mission_discovery_conf in discovery_configuration.survey_missions:
        if (
            mission_to_create := await _discover_survey_mission(
                session, project, survey_mission_discovery_conf, settings
            )
        ) is None:
            continue
        db_survey_mission = await survey_mission_ops.create_survey_mission(
            request_id=request_id,
            to_create=mission_to_create,
            initiator=user,
            session=session,
            event_dispatcher=event_dispatcher,
        )
        yield db_survey_mission


async def _discover_survey_mission(
    session: AsyncSession,
    project: models.Project,
    survey_mission_discovery_conf: discovery_schemas.SurveyMissionDiscoveryConfiguration,
    settings: config.SeisLabDataSettings,
    owner: user_schemas.User | None = None,
) -> mission_schemas.SurveyMissionCreate | None:
    mission_path = Path(
        "/".join(
            (
                str(settings.readonly_archive_root_directory).rstrip("/"),
                project.root_path.strip("/"),
                survey_mission_discovery_conf.relative_path.strip("/"),
            )
        )
    )
    logger.debug(f"{mission_path=}")
    if not await mission_path.is_dir():
        return None
    project_id = identifiers.ProjectId(project.id)
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
    return mission_schemas.SurveyMissionCreate(  # noqa
        id=identifiers.SurveyMissionId(uuid.uuid4()),
        owner_id=identifiers.UserId(owner.id if owner else project.owner_id),
        project_id=project_id,
        name=common.LocalizableDraftName(**survey_mission_discovery_conf.name),
        description=common.LocalizableDraftDescription(
            **(survey_mission_discovery_conf.description or {})
        ),
        relative_path=survey_mission_discovery_conf.relative_path,
    )


async def run_project_discovery(
    *,
    request_id: identifiers.RequestId,
    project_id: identifiers.ProjectId,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
    user: user_schemas.User,
) -> None:
    try:
        if (project := await project_queries.get_project(session, project_id)) is None:
            raise errors.SeisLabDataError(
                f"Project with id {project_id} does not exist."
            )
        if not permissions.can_discover_project(user, project):
            raise errors.SeisLabDataError(
                "User is not allowed to run discovery on this project."
            )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ProjectDiscoveryFailedEvent(
                request_id=request_id,
                project_id=project_id,
                initiator=user.id if user else "",
                details=str(err),
            )
        )
        return

    db_project = await project_ops.change_project_status(
        request_id=request_id,
        target_status=constants.ProjectStatus.UNDER_DISCOVERY,
        project_id=project_id,
        initiator=user,
        session=session,
        event_dispatcher=event_dispatcher,
    )

    try:
        async for db_survey_mission in discover_project_survey_missions(
            request_id=request_id,
            session=session,
            project=db_project,
            event_dispatcher=event_dispatcher,
            settings=settings,
            user=user,
        ):
            survey_mission_id = identifiers.SurveyMissionId(db_survey_mission.id)
            await event_dispatcher(
                event_schemas.ProjectDiscoveryProgressEvent(
                    project_id=project_id,
                    details=f"Discovered survey mission {db_survey_mission.id}",
                    initiator=user.id if user else "",
                )
            )
            await survey_mission_ops.change_survey_mission_status(
                request_id=request_id,
                target_status=constants.SurveyMissionStatus.UNDER_DISCOVERY,
                survey_mission_id=survey_mission_id,
                initiator=user,
                session=session,
                event_dispatcher=event_dispatcher,
            )

            try:
                async for _ in discover_survey_mission_records(
                    request_id=request_id,
                    session=session,
                    archive_root=str(settings.readonly_archive_root_directory),
                    survey_mission=db_survey_mission,
                    event_dispatcher=event_dispatcher,
                    user=user,
                ):
                    pass
            finally:
                await survey_mission_ops.change_survey_mission_status(
                    request_id=request_id,
                    target_status=constants.SurveyMissionStatus.DRAFT,
                    survey_mission_id=survey_mission_id,
                    initiator=user,
                    session=session,
                    event_dispatcher=event_dispatcher,
                )
    finally:
        await project_ops.change_project_status(
            request_id=request_id,
            target_status=constants.ProjectStatus.DRAFT,
            project_id=project_id,
            initiator=user,
            session=session,
            event_dispatcher=event_dispatcher,
        )
