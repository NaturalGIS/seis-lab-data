import logging
import uuid

import shapely
from anyio import to_thread
from geoalchemy2 import WKBElement
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    constants,
)
from ..db import models
from ..db.commands import (
    projects as project_commands,
    recordassets as asset_commands,
    surveymissions as mission_commands,
    surveyrelatedrecords as record_commands,
)
from ..db.queries import surveyrelatedrecords as record_queries
from ..schemas import (
    events as event_schemas,
    identifiers,
    surveyrelatedrecords as record_schemas,
    user as user_schemas,
)
from .. import dispatch
from ..tasks.derivers import (
    bbox_thumbnail,
    dispatch as deriver_dispatch,
)

logger = logging.getLogger(__name__)


async def collect_survey_mission_records_missing_previews(
    session: AsyncSession,
    survey_mission_id: identifiers.SurveyMissionId,
) -> list[identifiers.SurveyRelatedRecordId]:
    """Collect the ids of the records of a survey mission which have no previews.

    Records which already have derived assets are left out, so generating the
    mission's previews again only derives what is still missing: the previews
    of new records and of those whose generation failed before.
    """
    # no permission check, unlike user-facing operations: generation is
    # system-initiated, authorized when the discovery that enqueued it ran
    missing = []
    for record_id in await record_queries.collect_all_survey_mission_record_ids(
        session, survey_mission_id
    ):
        if (
            record := await record_queries.get_survey_related_record(session, record_id)
        ) is None:  # deleted in the meantime
            continue
        if any(
            constants.AssetType.DATA not in asset.asset_type for asset in record.assets
        ):
            continue
        missing.append(record_id)
    return missing


async def generate_record_previews(
    *,
    request_id: identifiers.RequestId,
    survey_related_record: models.SurveyRelatedRecord,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
) -> None:
    """Generate previews of a record's data assets, stored as derived assets.

    A new generation replaces the record's existing derived assets. Previews
    are best-effort: a file which cannot be rendered is logged and skipped,
    both because the archive holds corrupt files and because no record's state
    may depend on them.
    """
    record_id = identifiers.SurveyRelatedRecordId(survey_related_record.id)
    if (original_status := survey_related_record.status) not in (
        constants.SurveyRelatedRecordStatus.DRAFT,
        constants.SurveyRelatedRecordStatus.PUBLISHED,
    ):
        logger.warning(
            f"Survey-related record {record_id} is {original_status} - not "
            f"generating its previews..."
        )
        return
    if (
        discovery_configuration := survey_related_record.asset_discovery_configuration
    ) is None or not discovery_configuration.generate_previews:
        logger.debug(
            f"Survey-related record {record_id} does not come from a discovery "
            f"configuration that generates previews - not generating them..."
        )
        return
    mission_root_path = "/".join(
        (
            str(settings.readonly_archive_root_directory),
            survey_related_record.survey_mission.relative_path,
        )
    )
    derived = []
    for asset in survey_related_record.assets:
        if constants.AssetType.DATA not in asset.asset_type:
            continue
        if asset.relative_path is None:
            continue
        # paths typed by hand are not checked, and a '..' segment leaves the archive
        if ".." in asset.relative_path.split("/"):
            logger.debug(
                f"Asset path {asset.relative_path!r} points outside the archive - "
                f"not generating its preview..."
            )
            continue
        asset_path = "/".join((mission_root_path, asset.relative_path))
        if not deriver_dispatch.can_derive(asset_path):
            continue
        try:
            preview = await to_thread.run_sync(
                deriver_dispatch.dispatch_deriver,
                asset_path,
                survey_related_record.survey_mission.implicit_crs,
            )
        except Exception as err:
            logger.warning(f"Preview generation failed for {asset_path!r}: {err}")
            continue
        if preview is None:  # the file went away between the two checks
            continue
        # asset names may use the full 100-char cap; leave room for the labels
        source_name = asset.name[:80]
        derived.append(
            record_schemas.DerivedRecordAssetCreate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                name=f"{source_name} preview",
                description="",
                media_type="image/webp",
                # a single image serves both the list thumbnail and the map overlay
                asset_type=[
                    constants.AssetType.THUMBNAIL,
                    constants.AssetType.PREVIEW,
                ],
                data=preview.image,
            )
        )
    if not derived:
        logger.debug(
            f"No preview could be generated for record {record_id} - "
            f"leaving its existing assets alone..."
        )
        return
    # the record is only held under derivation while its derived assets are
    # replaced, never during the render, so a worker killed mid-render cannot
    # leave it stranded. The flip expects the status the record was fetched
    # with: one that moved meanwhile means the record was touched and the
    # previews may be stale
    if not await record_commands.compare_and_set_survey_related_record_status(
        session,
        record_id,
        original_status,
        constants.SurveyRelatedRecordStatus.UNDER_DERIVATION,
    ):
        logger.warning(
            f"Survey-related record {record_id} changed status while its "
            f"previews were being rendered - not storing them..."
        )
        return
    try:
        await asset_commands.replace_derived_record_assets(
            session, survey_related_record, derived
        )
    finally:
        # conditional as well, so as not to undo a status which something else,
        # such as the bulk publication of the mission, has set meanwhile
        await record_commands.compare_and_set_survey_related_record_status(
            session,
            record_id,
            constants.SurveyRelatedRecordStatus.UNDER_DERIVATION,
            original_status,
        )
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.RECORD,
            resource_id=str(record_id),
            modification=constants.ResourceModification.UPDATED,
            succeeded=True,
        )
    )


async def generate_project_thumbnail(
    *,
    request_id: identifiers.RequestId,
    project: models.Project,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
) -> None:
    """Render the project's bbox over the base map and store it as its thumbnail."""
    project_id = identifiers.ProjectId(project.id)
    if project.bbox_4326 is None:
        # removed after the task was enqueued, the removal cleared the thumbnail too
        logger.warning(
            f"Project {project_id} no longer has a bbox - not generating its "
            f"thumbnail..."
        )
        return
    thumbnail = await _render_bbox_thumbnail(project.bbox_4326, settings)
    if not await project_commands.set_project_thumbnail(session, project_id, thumbnail):
        logger.warning(
            f"Project {project_id} no longer exists - not storing its thumbnail..."
        )
        return
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.PROJECT,
            resource_id=str(project_id),
            modification=constants.ResourceModification.UPDATED,
            succeeded=True,
        )
    )


async def generate_survey_mission_thumbnail(
    *,
    request_id: identifiers.RequestId,
    survey_mission: models.SurveyMission,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
) -> None:
    """Render the mission's bbox over the base map and store it as its thumbnail."""
    survey_mission_id = identifiers.SurveyMissionId(survey_mission.id)
    if survey_mission.bbox_4326 is None:
        # removed after the task was enqueued, the removal cleared the thumbnail too
        logger.warning(
            f"Survey mission {survey_mission_id} no longer has a bbox - not "
            f"generating its thumbnail..."
        )
        return
    thumbnail = await _render_bbox_thumbnail(survey_mission.bbox_4326, settings)
    if not await mission_commands.set_survey_mission_thumbnail(
        session, survey_mission_id, thumbnail
    ):
        logger.warning(
            f"Survey mission {survey_mission_id} no longer exists - not storing "
            f"its thumbnail..."
        )
        return
    await event_dispatcher(
        event_schemas.ResourceModificationEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.MISSION,
            resource_id=str(survey_mission_id),
            modification=constants.ResourceModification.UPDATED,
            succeeded=True,
        )
    )


async def _render_bbox_thumbnail(
    bbox_4326: WKBElement, settings: config.SeisLabDataSettings
) -> bytes:
    if (tile_url_template := settings.thumbnail_base_tile_layer_url) is None:
        raise RuntimeError(
            "No base tile layer to render thumbnails with, set "
            "SEIS_LAB_DATA__THUMBNAIL_BASE_TILE_LAYER_URL"
        )
    return await to_thread.run_sync(
        bbox_thumbnail.render_bbox_thumbnail,
        bbox_thumbnail.build_tms_basemap_xml(
            tile_url_template, settings.webmap_base_tile_layer_max_zoom
        ),
        shapely.from_wkb(bbox_4326.data).bounds,
        bbox_thumbnail.BboxStyle(
            fill_color=settings.webmap_default_polygon_fill_color,
            fill_opacity=settings.webmap_default_polygon_fill_opacity,
            outline_color=settings.webmap_default_polygon_outline_color,
            outline_opacity=settings.webmap_default_polygon_outline_opacity,
            outline_width=settings.webmap_default_polygon_outline_width,
        ),
    )
