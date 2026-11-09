import dataclasses
import json
import logging
import math
import re
import uuid
from collections.abc import AsyncIterator
from typing import AsyncGenerator

import shapely
from anyio import Path, to_thread
from osgeo import osr
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    constants,
    errors,
)
from ..db import models
from ..db.queries import (
    discovery as discovery_queries,
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
    recordassets as asset_queries,
)
from ..db.commands import discovery as discovery_commands
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
from .. import dispatch
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

    logger.debug(f"Discovering contents of mission {mission.name!r}...")
    asset_discovery_configs = (
        await discovery_queries.collect_all_asset_discovery_configurations(session)
    )
    await mission_ops.change_survey_mission_status(
        request_id=request_id,
        target_status=constants.SurveyMissionStatus.UNDER_DISCOVERY,
        survey_mission_id=mission_id,
        initiator=user,
        session=session,
        event_dispatcher=event_dispatcher,
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
    try:
        await _discover_mission_records(
            request_id=request_id,
            mission=mission,
            session=session,
            event_dispatcher=event_dispatcher,
            settings=settings,
            user=user,
            asset_discovery_configs=asset_discovery_configs,
        )
    except FileNotFoundError as err:
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
    else:
        await event_dispatcher(
            event_schemas.DiscoveryEvent(
                initiator=user.id,
                resource_type=constants.ResourceType.MISSION,
                resource_id=str(mission_id),
                request_id=request_id,
                modification=constants.DiscoveryStage.ENDED,
                succeeded=True,
            )
        )
        # previews are derived by an operation of their own, which discovery
        # only kicks off once all of the mission's records exist
        preview_tasks.generate_mission_previews.send(
            raw_request_id=str(request_id),
            raw_survey_mission_id=str(mission.id),
            raw_initiator=json.dumps(dataclasses.asdict(user)),
        )
    finally:
        await mission_ops.change_survey_mission_status(
            request_id=request_id,
            target_status=constants.SurveyMissionStatus.DRAFT,
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
) -> None:
    mission_root_path = Path(
        "/".join(
            (
                str(settings.readonly_archive_root_directory),
                mission.relative_path,
            )
        )
    )
    logger.debug(f"{mission_root_path=}")
    # under a geographic CRS a re-read can never place metre coordinates
    heal_enabled = _is_projected_crs(mission.implicit_crs)
    if not heal_enabled:
        logger.info(
            "Records without a bbox are not read again: the mission's EPSG:%s is not "
            "a projected CRS",
            mission.implicit_crs,
        )
    # configurations overlap, so a file is found more than once, but read once
    attempted_record_ids: set[identifiers.SurveyRelatedRecordId] = set()
    for asset_discovery_conf in asset_discovery_configs:
        logger.debug(f"Searching for asset {asset_discovery_conf=}...")
        full_path_regexp = "/".join(
            (
                str(mission_root_path),
                asset_discovery_conf.relative_path_regexp,
            )
        )
        logger.debug(f"{full_path_regexp=}")
        async for found_path in _discover_asset_paths(full_path_regexp):
            # each found_path is to become a record with a single asset
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
                # create a new record and a new asset
                await record_ops.create_survey_related_record(
                    request_id=request_id,
                    to_create=record_schemas.SurveyRelatedRecordCreate(
                        id=record_id,
                        survey_mission_id=identifiers.SurveyMissionId(mission.id),
                        name=found_path.name,
                        description=metadata.describe() if metadata is not None else "",
                        dataset_category_id=identifiers.DatasetCategoryId(
                            asset_discovery_conf.dataset_category_id
                        ),
                        workflow_stage_id=identifiers.WorkflowStageId(
                            asset_discovery_conf.workflow_stage_id
                        ),
                        asset_discovery_configuration_id=identifiers.AssetDiscoveryConfId(
                            asset_discovery_conf.id
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
                                name=found_path.stem,
                                description="",
                                relative_path=relative_file_path,
                            )
                        ],
                    ),
                    initiator=user,
                    session=session,
                    event_dispatcher=event_dispatcher,
                )
            else:
                logger.debug(f"file {found_path!r} is already tracked in the DB")
                # records discovered before the configuration was stored on them
                # get it now, which makes them eligible for previews
                tracked_record = tracked_asset.survey_related_record
                if tracked_record.asset_discovery_configuration_id is None:
                    tracked_record.asset_discovery_configuration_id = (
                        asset_discovery_conf.id
                    )
                    session.add(tracked_record)
                    await session.commit()
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
    """Read once more the file of a tracked record that has no bbox.

    Nothing is written unless the file now gets a bbox.
    Then the bbox, description and dates are replaced, as on a manual update.
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
    """Create a record by hand, enriched by the discovery pipeline first.

    The record adopts the discovery configuration matching its data asset paths.
    The description and extents from its first data file override the payload's.
    Its previews are enqueued once it exists.
    """
    survey_mission = await mission_queries.get_survey_mission(
        session, to_create.survey_mission_id
    )
    # a failed check is left to the record operation, which emits the event
    if survey_mission is not None and (
        record_permissions.can_create_survey_related_record(initiator, survey_mission)
    ):
        fields = await _discover_record_fields(
            session,
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
    """Update a record by hand, re-running discovery when its data files change.

    Only a different set of data asset paths runs the pipeline.
    The record then adopts a configuration anew and the metadata of its first file.
    Its previews are enqueued again.
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
            session, survey_related_record.survey_mission, proposed_paths, settings
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
    session: AsyncSession,
    survey_mission: models.SurveyMission,
    data_asset_paths: list[str | None],
    settings: config.SeisLabDataSettings,
) -> dict:
    """Run the discovery pipeline over the data asset paths of a manual record.

    The returned fields override the record's.
    The configuration is always returned, None when no path matches.
    The description and extents only when extraction produced them.
    Otherwise the record keeps its own.
    """
    # a '..' segment would lead adoption and the extractor out of the archive
    usable_paths = [
        path for path in data_asset_paths if path and ".." not in path.split("/")
    ]
    configurations = await discovery_queries.collect_all_asset_discovery_configurations(
        session
    )
    # configurations come in name order, and the first path that matches decides
    adopted_configuration = next(
        (
            configuration
            for path in usable_paths
            for configuration in configurations
            if path_matches_discovery_pattern(configuration.relative_path_regexp, path)
        ),
        None,
    )
    fields = {
        "asset_discovery_configuration_id": (
            adopted_configuration.id if adopted_configuration is not None else None
        )
    }
    if not usable_paths:
        return fields
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
    return fields | _extracted_record_fields(metadata, bbox_wkt)


def _extracted_record_fields(
    metadata: extractor_schemas.ExtractionResult | None, bbox_wkt: str | None
) -> dict:
    """The record fields an extraction produced, which replace the record's own."""
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
    """Extract a file's metadata and its lon/lat bbox as WKT.

    Best-effort: a failure must never abort discovery or record creation.
    It is logged and comes out as None.
    A file without a CRS takes the one its SEG-Y header quotes, else the mission's.
    The metadata then names the CRS that placed it.
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
    applied_crs_name = None
    if metadata is not None:
        bbox_4326 = metadata.bbox_4326
        if (native_bbox := metadata.bbox_native_needing_crs) is not None:
            header_crs = _header_crs(metadata)
            applied_crs = header_crs if header_crs is not None else implicit_crs
            if header_crs is not None and header_crs != implicit_crs:
                logger.info(
                    "Applying EPSG:%s from the header of %s instead of the mission's "
                    "EPSG:%s",
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
    """The projected CRS a SEG-Y header quotes, when it quotes exactly one.

    Several leave the choice open, so none of them is taken.
    """
    if not isinstance(metadata, extractor_schemas.SegyMetadata):
        return None
    projected_codes = {
        code for code in metadata.header_epsg_codes if _is_projected_crs(code)
    }
    return projected_codes.pop() if len(projected_codes) == 1 else None


def _is_projected_crs(epsg: int) -> bool:
    """Tell whether an EPSG code is a projected CRS, the only kind that places metres.

    An unknown code is not one.
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
    """Turn an extracted lon/lat bbox into a WKT polygon for the record.

    Garbage coordinates (non-finite or out of lon/lat range, e.g. from a bogus
    CRS transform) are discarded with a warning. The surviving bbox is expanded
    by _BBOX_BUFFER on every side. Antimeridian-crossing bboxes are not handled
    (Portuguese waters).
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
    """Discover assets for a particular asset discovery configuration.

    Discovery assumptions:

    - One record only holds one asset. Although generally we support multiple assets per record,
      for discovery the only supported use case is a 1:1 mapping between record and asset.
    """
    root, pattern = split_pattern_path(full_path_regexp)
    if not pattern:
        if await root.is_file():
            yield root
        return

    pattern_parts = Path(pattern).parts
    async for matched_path in walk_pattern(root, pattern_parts):
        yield matched_path


async def walk_pattern(
    current: Path, remaining: tuple[str, ...]
) -> AsyncIterator[Path]:
    if not remaining:
        if await current.is_file():
            yield current
        return

    head, *tail = remaining
    tail = tuple(tail)
    regex = re.compile(f"^{head}$")
    try:
        async for entry in current.iterdir():
            if await entry.is_dir():
                async for matched in walk_pattern(entry, remaining):
                    yield matched
            if regex.match(entry.name):
                if tail:
                    async for matched in walk_pattern(entry, tail):
                        yield matched
                else:
                    if await entry.is_file():
                        yield entry
    except (PermissionError, NotADirectoryError):
        return


def split_pattern_path(regexp_path: str) -> tuple[Path, str]:
    """Split a regexp path into a Path component and a regexp pattern"""
    _re_meta = re.compile(r"[.*+?^${}()\[\]|\\]")
    parts = Path(regexp_path).parts
    plain_parts = []
    for i, part in enumerate(parts):
        if _re_meta.search(part):
            pattern = str(Path(*parts[i:])) if parts[i:] else ""
            return Path(*plain_parts) if plain_parts else Path("."), pattern
        plain_parts.append(part)
    return Path(regexp_path), ""


def path_matches_discovery_pattern(
    relative_path_regexp: str, relative_path: str
) -> bool:
    """Tell whether discovery would find a mission-relative file path.

    Mirrors `walk_pattern` without touching the disk.
    The pattern's literal prefix is fixed at the mission root.
    Its last segment matches the file name, the others match directories in order.
    Any directory may be skipped before, between or after the matched ones.
    """
    # the walk joins mission_root + "/" + regexp, and Path collapses a leading slash
    prefix, pattern = split_pattern_path(relative_path_regexp.lstrip("/"))
    path_parts = Path(relative_path.lstrip("/")).parts
    prefix_parts = prefix.parts
    if path_parts[: len(prefix_parts)] != prefix_parts:
        return False
    remaining_parts = path_parts[len(prefix_parts) :]
    if not pattern:
        return remaining_parts == ()
    if not remaining_parts:
        return False
    *directory_patterns, file_name_pattern = Path(pattern).parts
    *directories, file_name = remaining_parts
    # configuration regexps are never validated; a bad one must not block manual saves
    try:
        # match rather than fullmatch, as in walk_pattern: `^a|b$` is not the same
        file_name_regex = re.compile(f"^{file_name_pattern}$")
        directory_regexes = [re.compile(f"^{p}$") for p in directory_patterns]
    except re.error as err:
        logger.warning(
            "Invalid discovery configuration pattern %r: %s", relative_path_regexp, err
        )
        return False
    if not file_name_regex.match(file_name):
        return False
    # each directory pattern consumes the directories up to the one it matches
    unmatched_directories = iter(directories)
    for regex in directory_regexes:
        if not any(regex.match(directory) for directory in unmatched_directories):
            return False
    return True
