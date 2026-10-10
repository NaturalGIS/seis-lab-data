import json
import logging
import uuid

import shapely
from anyio import Path, to_thread
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    constants,
)
from ..db import models
from ..db.commands import (
    recordassets as asset_commands,
    surveyrelatedrecords as record_commands,
)
from ..db.queries import surveyrelatedrecords as record_queries
from ..schemas import (
    common,
    events as event_schemas,
    identifiers,
    surveyrelatedrecords as record_schemas,
    user as user_schemas,
)
from .. import dispatch
from ..tasks.derivers import dispatch as deriver_dispatch

logger = logging.getLogger(__name__)


async def load_preview_directories(
    settings: config.SeisLabDataSettings,
) -> frozenset[str]:
    """Read the family/stage directory prefixes which gate preview generation."""
    contents = await Path(settings.preview_directories_path).read_text()
    return frozenset(json.loads(contents)["directories"])


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
    directory_prefixes: frozenset[str],
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
        asset_path = "/".join((mission_root_path, asset.relative_path))
        if not deriver_dispatch.is_previewable(
            asset_path, asset.relative_path, directory_prefixes
        ):
            continue
        try:
            preview = await to_thread.run_sync(
                deriver_dispatch.dispatch_deriver, asset_path
            )
        except Exception as err:
            logger.warning(f"Preview generation failed for {asset_path!r}: {err}")
            continue
        if preview is None:  # the file went away between the two checks
            continue
        # asset names may use the full 100-char cap; leave room for the labels
        source_name = asset.name["en"][:80]
        derived.append(
            record_schemas.DerivedRecordAssetCreate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                name=common.LocalizableDraftName(
                    en=f"{source_name} preview",
                    pt=f"Pré-visualização de {source_name}",
                ),
                description=common.LocalizableDraftDescription(en="", pt=""),
                media_type="image/webp",
                # a single image serves both the list thumbnail and the map overlay
                asset_type=[
                    constants.AssetType.THUMBNAIL,
                    constants.AssetType.PREVIEW,
                ],
                data=preview.image,
                geog=shapely.box(*preview.bounds_4326).wkt,
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
