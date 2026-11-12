import asyncio
import dataclasses
import json
import logging
import math
import uuid
from typing import AsyncGenerator

import shapely
from anyio import Path, to_thread
from osgeo import osr
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    constants,
    dispatch,
    errors,
    pathpatterns,
)
from ..db import models
from ..db.queries import (
    discovery as discovery_queries,
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
    recordassets as asset_queries,
)
from ..db.commands import (
    discovery as discovery_commands,
    surveymissions as mission_commands,
)
from ..permissions import (
    discovery as discovery_permissions,
    surveymissions as mission_permissions,
    surveyrelatedrecords as record_permissions,
)
from ..schemas import (
    events as event_schemas,
    discovery as discovery_schemas,
    identifiers,
    surveyrelatedrecords as record_schemas,
    user as user_schemas,
)
from ..tasks import previews as preview_tasks
from ..tasks.extractors import (
    common as extractor_common,
    dispatch as extractor_dispatch,
    schemas as extractor_schemas,
)

from . import (
    surveymissions as mission_ops,
    surveyrelatedrecords as record_ops,
)

logger = logging.getLogger(__name__)

# Buffer applied to every extracted bbox (~10 m in degrees): noise on multi-km
# footprints, but keeps point/line extents visible on the map and avoids the
# degenerate zero-area polygons that shapely marks invalid.
_BBOX_BUFFER = 1e-4


async def create_asset_discovery_configuration(
    *,
    request_id: identifiers.RequestId,
    to_create: discovery_schemas.AssetDiscoveryConfigurationCreate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.AssetDiscoveryConfiguration | None:
    try:
        if not discovery_permissions.can_create_asset_discovery_configuration(
            initiator
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to create an asset discovery configuration."
            )
        asset_discovery_configuration = (
            await discovery_commands.create_asset_discovery_configuration(
                session, to_create
            )
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
                resource_id=None,
                modification=constants.ResourceModification.CREATED,
                succeeded=False,
                details=str(err),
            )
        )
        return None

    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            modification=constants.ResourceModification.CREATED,
            succeeded=True,
            resource_id=str(asset_discovery_configuration.id),
        )
    )
    return asset_discovery_configuration


async def update_asset_discovery_configuration(
    request_id: identifiers.RequestId,
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId,
    to_update: discovery_schemas.AssetDiscoveryConfigurationUpdate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> models.AssetDiscoveryConfiguration | None:
    try:
        if (
            asset_discovery_conf
            := await discovery_queries.get_asset_discovery_configuration(
                session, asset_discovery_configuration_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                f"asset discovery configuration with id {asset_discovery_configuration_id} does not exist."
            )
        if not discovery_permissions.can_update_asset_discovery_configuration(
            initiator
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to update asset discovery configuration."
            )
        updated_asset_discovery_conf = (
            await discovery_commands.update_asset_discovery_configuration(
                session, asset_discovery_conf, to_update
            )
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
                resource_id=str(asset_discovery_configuration_id),
                modification=constants.ResourceModification.UPDATED,
                succeeded=False,
                details=str(err),
            )
        )
        return None

    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            resource_id=str(asset_discovery_configuration_id),
            modification=constants.ResourceModification.UPDATED,
            succeeded=True,
        )
    )
    return updated_asset_discovery_conf


async def delete_asset_discovery_configuration(
    *,
    request_id: identifiers.RequestId,
    asset_discovery_configuration_id: identifiers.AssetDiscoveryConfId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    try:
        if (
            await discovery_queries.get_asset_discovery_configuration(
                session, asset_discovery_configuration_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                f"asset discovery configuration with id {asset_discovery_configuration_id} does not exist."
            )
        if not discovery_permissions.can_delete_asset_discovery_configuration(
            initiator
        ):
            raise errors.SeisLabDataError(
                "User is not allowed to delete asset discovery configuration."
            )
        await discovery_commands.delete_asset_discovery_configuration(
            session, asset_discovery_configuration_id
        )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.ResourceModificationEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
                resource_id=str(asset_discovery_configuration_id),
                modification=constants.ResourceModification.DELETED,
                succeeded=False,
                details=str(err),
            ),
        )
        return None

    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.ASSET_DISCOVERY_CONFIG,
            resource_id=str(asset_discovery_configuration_id),
            modification=constants.ResourceModification.DELETED,
            succeeded=True,
        ),
    )


async def run_mission_discovery(
    *,
    request_id: identifiers.RequestId,
    mission_id: identifiers.SurveyMissionId,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
    user: user_schemas.User,
) -> None:
    try:
        if (
            mission := await mission_queries.get_survey_mission(session, mission_id)
        ) is None:
            raise errors.SeisLabDataError(
                f"Survey mission with id {mission_id} does not exist."
            )
        if not mission_permissions.can_discover_survey_mission(user, mission):
            raise errors.SeisLabDataError(
                "User is not allowed to run discovery on this survey mission."
            )
        if (mission_status := mission.status) not in (
            constants.SurveyMissionStatus.DRAFT,
            constants.SurveyMissionStatus.PUBLISHED,
        ):
            raise errors.SeisLabDataError(
                f"Cannot run discovery on survey mission because its status is "
                f"{mission_status}"
            )
        if not await mission_commands.compare_and_set_survey_mission_status(
            session,
            mission_id,
            mission_status,
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
        ):
            raise errors.SeisLabDataError(
                "Cannot run discovery on survey mission because its status "
                "changed meanwhile"
            )
    except errors.SeisLabDataError as err:
        await event_dispatcher(
            event_schemas.DiscoveryEvent(
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                request_id=request_id,
                modification=constants.DiscoveryStage.ENDED,
                succeeded=False,
                details=str(err),
            )
        )
        return

    # from here on the mission is under discovery, and every way out of the
    # block below must report the end of the run and give the mission back its
    # status
    try:
        logger.debug(f"Discovering contents of mission {mission.name!r}...")
        asset_discovery_configs = (
            await discovery_queries.collect_all_asset_discovery_configurations(session)
        )
        # when there is a failure, the db session is rolled back, expiring everything it
        # holds; we dettach the mission and asset discovery confs in order to
        # keep them alive
        session.expunge(mission)
        for asset_discovery_conf in asset_discovery_configs:
            session.expunge(asset_discovery_conf)
        await event_dispatcher(
            event_schemas.ResourceStatusChangedEvent(
                request_id=request_id,
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                succeeded=True,
                new_status=constants.SurveyMissionStatus.UNDER_DISCOVERY,
            )
        )
        await event_dispatcher(
            event_schemas.DiscoveryEvent(
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                request_id=request_id,
                modification=constants.DiscoveryStage.STARTED,
                succeeded=True,
            )
        )
        summary = await _discover_mission_records(
            request_id=request_id,
            mission=mission,
            session=session,
            event_dispatcher=event_dispatcher,
            settings=settings,
            user=user,
            asset_discovery_configs=asset_discovery_configs,
        )
    # raised into the run when dramatiq interrupts it, e.g. at its time limit
    except asyncio.CancelledError:
        logger.warning(f"Discovery of mission {mission_id} was interrupted")
        await event_dispatcher(
            event_schemas.DiscoveryEvent(
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                request_id=request_id,
                modification=constants.DiscoveryStage.ENDED,
                succeeded=False,
                details=(
                    "discovery was interrupted - the records created so far are "
                    "kept, run it again to resume"
                ),
            )
        )
        raise
    except Exception as err:
        logger.exception(f"Discovery of mission {mission_id} failed")
        await event_dispatcher(
            event_schemas.DiscoveryEvent(
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                request_id=request_id,
                modification=constants.DiscoveryStage.ENDED,
                succeeded=False,
                # anything else may carry internals, such as SQL, which stay in the logs
                details=(
                    str(err)
                    if isinstance(err, (errors.SeisLabDataError, FileNotFoundError))
                    else f"unexpected error ({type(err).__name__})"
                ),
            )
        )
    else:
        await event_dispatcher(
            event_schemas.DiscoveryEvent(
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                request_id=request_id,
                modification=constants.DiscoveryStage.ENDED,
                succeeded=True,
                details=summary,
            )
        )
        # previews are derived by an operation of their own, which discovery
        # only kicks off once all of the mission's records exist
        preview_tasks.generate_mission_previews.send(
            raw_request_id=str(request_id),
            raw_survey_mission_id=str(mission_id),
            raw_initiator=json.dumps(dataclasses.asdict(user)),
        )
    finally:
        # whatever was left half-done must not be committed with the status
        await session.rollback()
        await mission_ops.change_survey_mission_status(
            request_id=request_id,
            target_status=mission_status,
            survey_mission_id=mission_id,
            initiator=user,
            session=session,
            event_dispatcher=event_dispatcher,
        )


async def _discover_mission_records(
    *,
    request_id: identifiers.RequestId,
    mission: models.SurveyMission,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
    user: user_schemas.User,
    asset_discovery_configs: list[models.AssetDiscoveryConfiguration],
) -> str:
    """Create records for the mission files that match asset discovery configurations.

    Each configuration's path pattern is searched under the mission's directory.
    A file or a configuration whose processing raises an error is logged and skipped.

    Returns a summary with the number of records created and of the files and
    configurations that failed.
    """
    mission_root_path = Path(
        "/".join(
            (
                str(settings.readonly_archive_root_directory),
                mission.relative_path,
            )
        )
    )
    logger.debug(f"{mission_root_path=}")
    # without the mission's directory there is nothing to search
    if not await mission_root_path.is_dir():
        raise FileNotFoundError(
            f"The mission's directory {mission.relative_path!r} is not in the archive"
        )
    # under a geographic CRS only a header code could place metres: not worth a re-read
    heal_enabled = _is_projected_crs(mission.implicit_crs)
    if not heal_enabled:
        logger.info(
            "Records without a bbox are not read again: the mission's EPSG:%s is not "
            "a projected CRS",
            mission.implicit_crs,
        )
    # configurations overlap, so a file is found more than once, but read once
    attempted_record_ids: set[identifiers.SurveyRelatedRecordId] = set()
    created_count = 0
    failed_paths: set[str] = set()
    failed_configuration_names: list[str] = []
    for asset_discovery_conf in asset_discovery_configs:
        logger.debug(f"Searching for asset {asset_discovery_conf=}...")
        full_path_regexp = "/".join(
            (
                str(mission_root_path),
                asset_discovery_conf.relative_path_regexp,
            )
        )
        logger.debug(f"{full_path_regexp=}")
        # e.g. an invalid regexp, or an archive mount that goes away mid-walk
        try:
            async for found_path in _discover_asset_paths(full_path_regexp):
                try:
                    if await _discover_file(
                        request_id=request_id,
                        found_path=found_path,
                        mission_root_path=mission_root_path,
                        mission=mission,
                        asset_discovery_conf=asset_discovery_conf,
                        heal_enabled=heal_enabled,
                        attempted_record_ids=attempted_record_ids,
                        session=session,
                        event_dispatcher=event_dispatcher,
                        user=user,
                    ):
                        created_count += 1
                except Exception:
                    logger.exception(f"Could not discover file {str(found_path)!r}")
                    failed_paths.add(str(found_path))
                    await session.rollback()
        except Exception:
            logger.exception(
                f"Could not search for the files of asset discovery configuration "
                f"{asset_discovery_conf.name!r}"
            )
            failed_configuration_names.append(asset_discovery_conf.name)
            await session.rollback()
    summary = f"{created_count} new records"
    if failed_paths:
        summary += f", {len(failed_paths)} files could not be discovered"
    if failed_configuration_names:
        summary += (
            f", searching failed for configurations "
            f"{', '.join(failed_configuration_names)}"
        )
    return summary


async def _discover_file(
    *,
    request_id: identifiers.RequestId,
    found_path: Path,
    mission_root_path: Path,
    mission: models.SurveyMission,
    asset_discovery_conf: models.AssetDiscoveryConfiguration,
    heal_enabled: bool,
    attempted_record_ids: set[identifiers.SurveyRelatedRecordId],
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    user: user_schemas.User,
) -> bool:
    """Create a record with a single data asset for a discovered file.

    If the file is already tracked, its record is healed instead, provided that
    healing is enabled, the record has no bbox and it was not attempted before.

    Returns True if a record was created.
    """
    relative_file_path = str(found_path.relative_to(mission_root_path))
    if (
        tracked_asset := await asset_queries.get_record_asset_by_file_path(
            session,
            relative_file_path,
            identifiers.SurveyMissionId(mission.id),
        )
    ) is None:
        metadata, bbox_wkt = await _extract_file_metadata(
            str(found_path), mission.implicit_crs
        )
        record_id = identifiers.SurveyRelatedRecordId(uuid.uuid4())
        attempted_record_ids.add(record_id)
        await record_ops.create_survey_related_record(
            request_id=request_id,
            to_create=record_schemas.SurveyRelatedRecordCreate(
                id=record_id,
                survey_mission_id=identifiers.SurveyMissionId(mission.id),
                # names are capped, the full file name lives on in the asset's path
                name=found_path.name[: constants.NAME_MAX_LENGTH],
                description=metadata.describe() if metadata is not None else "",
                dataset_category_id=identifiers.DatasetCategoryId(
                    asset_discovery_conf.dataset_category_id
                ),
                workflow_stage_id=identifiers.WorkflowStageId(
                    asset_discovery_conf.workflow_stage_id
                ),
                bbox_4326=bbox_wkt,
                temporal_extent_begin=(
                    metadata.temporal_extent_begin if metadata else None
                ),
                temporal_extent_end=(
                    metadata.temporal_extent_end if metadata else None
                ),
                assets=[
                    record_schemas.DataRecordAssetCreate(
                        id=identifiers.RecordAssetId(uuid.uuid4()),
                        name=found_path.stem[: constants.NAME_MAX_LENGTH],
                        description="",
                        relative_path=relative_file_path,
                    )
                ],
            ),
            initiator=user,
            session=session,
            event_dispatcher=event_dispatcher,
        )
        return True
    logger.debug(f"file {found_path!r} is already tracked in the DB")
    tracked_record = tracked_asset.survey_related_record
    record_id = identifiers.SurveyRelatedRecordId(
        tracked_asset.survey_related_record_id
    )
    # e.g. discovered while the mission's CRS was still the 4326 default
    if (
        heal_enabled
        and tracked_record.bbox_4326 is None
        and record_id not in attempted_record_ids
    ):
        attempted_record_ids.add(record_id)
        await _heal_record_without_bbox(
            request_id=request_id,
            record_id=record_id,
            tracked_record=tracked_record,
            file_path=str(found_path),
            implicit_crs=mission.implicit_crs,
            session=session,
            event_dispatcher=event_dispatcher,
            user=user,
        )
    return False


async def _heal_record_without_bbox(
    *,
    request_id: identifiers.RequestId,
    record_id: identifiers.SurveyRelatedRecordId,
    tracked_record: models.SurveyRelatedRecord,
    file_path: str,
    implicit_crs: int,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    user: user_schemas.User,
) -> None:
    """Re-extract the metadata of a tracked record that has no bbox.

    The record is updated only if the extraction yields a bbox. Its bbox, description
    and temporal extent are then replaced by the extracted values. A bbox set on the
    record while the extraction was running is kept, and the record is not updated.
    """
    metadata, bbox_wkt = await _extract_file_metadata(file_path, implicit_crs)
    if bbox_wkt is None:
        logger.debug(
            "%s still gives no bbox, record %s is left as it is", file_path, record_id
        )
        return
    # the extraction can take a minute, so the record is read again
    # expire_all() would also expire the mission and configurations (MissingGreenlet)
    session.expire(tracked_record)
    record = await record_queries.get_survey_related_record(session, record_id)
    # a bbox drawn by hand meanwhile wins
    if record is None or record.bbox_4326 is not None:
        return
    # the update deletes the data assets and relations its payload leaves out
    # (db/commands/surveyrelatedrecords.py), so all of them are restated
    current_assets_and_relations = {
        "assets": [
            {"id": asset.id}
            for asset in record.assets
            if constants.AssetType.DATA in asset.asset_type
        ],
        "related_records": [
            {"related_record_id": link.related_to_id, "relationship": link.relation}
            for link in record.related_to_links
        ],
    }
    to_update = record_schemas.SurveyRelatedRecordUpdate.model_validate(
        _extracted_record_fields(metadata, bbox_wkt) | current_assets_and_relations
    )
    try:
        await record_ops.update_survey_related_record(
            request_id=request_id,
            survey_related_record_id=record_id,
            to_update=to_update,
            initiator=user,
            session=session,
            event_dispatcher=event_dispatcher,
        )
    # a busy record must not abort the sweep, the next one tries it again
    except errors.SeisLabDataError as err:
        logger.warning(
            "Could not update record %s with the bbox of %s: %s",
            record_id,
            file_path,
            err,
        )


async def create_manual_survey_related_record(
    *,
    request_id: identifiers.RequestId,
    to_create: record_schemas.SurveyRelatedRecordCreate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
) -> models.SurveyRelatedRecord:
    """Create a record from user input, enriched with the metadata of its data files.

    The description and extents extracted from the first data asset path replace
    those of the payload. Preview generation is enqueued after the record is created.
    """
    survey_mission = await mission_queries.get_survey_mission(
        session, to_create.survey_mission_id
    )
    # a failed check is left to the record operation, which emits the event
    if survey_mission is not None and (
        record_permissions.can_create_survey_related_record(initiator, survey_mission)
    ):
        fields = await _discover_record_fields(
            survey_mission,
            [asset.relative_path for asset in to_create.assets],
            settings,
        )
        # validated again, as the extracted bbox comes as WKT
        to_create = record_schemas.SurveyRelatedRecordCreate.model_validate(
            to_create.model_dump() | fields
        )
    # extraction can take a minute: the record operation's guards must see fresh state
    session.expire_all()
    created_record = await record_ops.create_survey_related_record(
        request_id=request_id,
        to_create=to_create,
        initiator=initiator,
        session=session,
        event_dispatcher=event_dispatcher,
    )
    # whether the record gets previews is decided by the derivation itself
    preview_tasks.generate_record_previews.send(
        raw_request_id=str(request_id),
        raw_survey_related_record_id=str(to_create.id),
        raw_initiator=json.dumps(dataclasses.asdict(initiator)),
    )
    return created_record


async def update_manual_survey_related_record(
    *,
    request_id: identifiers.RequestId,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    to_update: record_schemas.SurveyRelatedRecordUpdate,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
) -> models.SurveyRelatedRecord:
    """Update a record from user input, re-extracting metadata if its data files change.

    Extraction runs only if the set of data asset paths differs from the stored one.
    The description and extents extracted from the first path then replace those of
    the payload, and preview generation is enqueued.
    """
    survey_related_record = await record_queries.get_survey_related_record(
        session, survey_related_record_id
    )
    proposed_paths = [asset.relative_path for asset in to_update.assets]
    paths_changed = survey_related_record is not None and set(proposed_paths) != {
        asset.relative_path
        for asset in survey_related_record.assets
        if constants.AssetType.DATA in asset.asset_type
    }
    # a failed check is left to the record operation, which emits the event
    if paths_changed and record_permissions.can_update_survey_related_record(
        initiator, survey_related_record
    ):
        fields = await _discover_record_fields(
            survey_related_record.survey_mission, proposed_paths, settings
        )
        # only the fields that were set, so that a partial update stays partial
        to_update = record_schemas.SurveyRelatedRecordUpdate.model_validate(
            to_update.model_dump(exclude_unset=True) | fields
        )
    # extraction can take a minute: the record operation's guards must see fresh state
    session.expire_all()
    updated_record = await record_ops.update_survey_related_record(
        request_id=request_id,
        survey_related_record_id=survey_related_record_id,
        to_update=to_update,
        initiator=initiator,
        session=session,
        event_dispatcher=event_dispatcher,
    )
    # previews only go stale with the data files, and a run redirects open edit forms
    if paths_changed:
        preview_tasks.generate_record_previews.send(
            raw_request_id=str(request_id),
            raw_survey_related_record_id=str(survey_related_record_id),
            raw_initiator=json.dumps(dataclasses.asdict(initiator)),
        )
    return updated_record


async def _discover_record_fields(
    survey_mission: models.SurveyMission,
    data_asset_paths: list[str | None],
    settings: config.SeisLabDataSettings,
) -> dict:
    """Extract record fields from the first usable data asset path.

    Empty paths and paths with a `..` segment are not usable.

    Returns the record fields produced by the extraction, empty if there is no usable
    path.
    """
    # a '..' segment would lead the extractor out of the archive
    usable_paths = [
        path for path in data_asset_paths if path and ".." not in path.split("/")
    ]
    if not usable_paths:
        return {}
    file_path = "/".join(
        (
            str(settings.readonly_archive_root_directory),
            survey_mission.relative_path,
            usable_paths[0],
        )
    )
    metadata, bbox_wkt = await _extract_file_metadata(
        file_path, survey_mission.implicit_crs
    )
    return _extracted_record_fields(metadata, bbox_wkt)


def _extracted_record_fields(
    metadata: extractor_schemas.ExtractionResult | None, bbox_wkt: str | None
) -> dict:
    """Build the record fields produced by a metadata extraction.

    Returns the bbox, the description and the temporal extent, each one only if the
    extraction produced it. The temporal extent requires both its begin and its end.
    """
    fields = {}
    if bbox_wkt is not None:
        fields["bbox_4326"] = bbox_wkt
    if metadata is None:
        return fields
    fields["description"] = metadata.describe()
    if (
        metadata.temporal_extent_begin is not None
        and metadata.temporal_extent_end is not None
    ):
        fields["temporal_extent_begin"] = metadata.temporal_extent_begin
        fields["temporal_extent_end"] = metadata.temporal_extent_end
    return fields


async def _extract_file_metadata(
    file_path: str, implicit_crs: int
) -> tuple[extractor_schemas.ExtractionResult | None, str | None]:
    """Extract a file's metadata and its EPSG:4326 bbox as WKT.

    Extraction errors are logged, and result in None metadata. A bbox extracted in
    native coordinates without a CRS is reprojected using the projected CRS declared
    in the SEG-Y header, if exactly one is declared, or `implicit_crs` otherwise.
    The metadata is then updated with the applied CRS.

    Returns the metadata and the bbox WKT, each of which may be None.
    """
    metadata = None
    try:
        metadata = await to_thread.run_sync(
            extractor_dispatch.dispatch_extractor, file_path
        )
    except Exception as err:
        logger.warning("Metadata extraction failed for %s: %s", file_path, err)
        logger.debug("Extraction failure detail", exc_info=True)
    bbox_4326 = None
    header_crs = None
    applied_crs = implicit_crs
    applied_crs_name = None
    if metadata is not None:
        bbox_4326 = metadata.bbox_4326
        if (native_bbox := metadata.bbox_native_needing_crs) is not None:
            header_crs = _header_crs(metadata)
            if header_crs is not None:
                applied_crs = header_crs
                if header_crs != implicit_crs:
                    logger.info(
                        "Applying EPSG:%s from the header of %s instead of the "
                        "mission's EPSG:%s",
                        header_crs,
                        file_path,
                        implicit_crs,
                    )
            try:
                srs = osr.SpatialReference()
                srs.ImportFromEPSG(applied_crs)
                bbox_4326 = extractor_common.project_bbox_to_wgs84(native_bbox, srs)
                applied_crs_name = srs.GetName()
            except Exception as err:
                logger.warning(
                    "Could not apply CRS EPSG:%s to %s: %s",
                    applied_crs,
                    file_path,
                    err,
                )
    bbox_wkt = _bbox_4326_tuple_to_wkt(bbox_4326) if bbox_4326 is not None else None
    if applied_crs_name is not None and bbox_wkt is not None:
        metadata = metadata.model_copy(
            update={
                "epsg": applied_crs,
                "crs_name": applied_crs_name,
                "crs_from_mission": header_crs is None,
            }
        )
    return metadata, bbox_wkt


def _header_crs(metadata: extractor_schemas.ExtractionResult) -> int | None:
    """Return the projected CRS declared in a SEG-Y header.

    Returns None if the metadata is not SEG-Y metadata, or if its header declares
    either no projected CRS or more than one.
    """
    if not isinstance(metadata, extractor_schemas.SegyMetadata):
        return None
    projected_codes = {
        code for code in metadata.header_epsg_codes if _is_projected_crs(code)
    }
    return projected_codes.pop() if len(projected_codes) == 1 else None


def _is_projected_crs(epsg: int) -> bool:
    """Check whether an EPSG code identifies a projected CRS.

    Returns False for unknown codes.
    """
    spatial_reference = osr.SpatialReference()
    try:
        spatial_reference.ImportFromEPSG(epsg)
    # OverflowError: values beyond a C int never reach PROJ
    except (RuntimeError, OverflowError):
        return False
    return bool(spatial_reference.IsProjected())


def _bbox_4326_tuple_to_wkt(
    bbox: tuple[float, float, float, float],
) -> str | None:
    """Convert an EPSG:4326 bbox tuple into a WKT polygon.

    Returns None, and logs a warning, if a coordinate is non-finite or outside the
    longitude/latitude range. Otherwise the bbox is expanded by `_BBOX_BUFFER` on
    every side and snapped to a 1e-5 degree grid. Bboxes crossing the antimeridian
    are not supported.
    """
    minx, miny, maxx, maxy = bbox
    tolerance = 1e-6
    if not all(math.isfinite(value) for value in bbox) or not (
        -180 - tolerance <= minx <= maxx <= 180 + tolerance
        and -90 - tolerance <= miny <= maxy <= 90 + tolerance
    ):
        logger.warning(
            "Discarding extracted bbox with out-of-range or non-finite coordinates: %s",
            bbox,
        )
        return None
    # The envelope of the two corners is always valid (Point, LineString or
    # Polygon), unlike shapely.box on a degenerate bbox; buffering with square
    # caps and mitre joins keeps the result an axis-aligned rectangle.
    envelope = shapely.MultiPoint([(minx, miny), (maxx, maxy)]).envelope
    buffered = envelope.buffer(_BBOX_BUFFER, cap_style="square", join_style="mitre")
    # Snap to a 1e-5 degree grid (~1 m): finer precision is meaningless under
    # the ~10 m buffer, and the frontend's TerraDraw silently rejects
    # coordinates with more than 9 decimal places, dropping the map rectangle.
    return shapely.set_precision(buffered, 1e-5).wkt


async def _discover_asset_paths(
    full_path_regexp: str,
) -> AsyncGenerator[Path, None]:
    """Yield the files that match a full path pattern."""
    root, pattern = pathpatterns.split_pattern_path(full_path_regexp)
    if not pattern:
        if await root.is_file():
            yield root
        return

    pattern_parts = Path(pattern).parts
    async for matched_path in pathpatterns.walk_pattern(root, pattern_parts):
        yield matched_path
