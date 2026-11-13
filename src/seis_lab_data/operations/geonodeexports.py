import datetime as dt
import logging
import re
import pathlib

import httpx
from anyio import Path
from sqlmodel.ext.asyncio.session import AsyncSession

from .. import (
    config,
    constants,
    dispatch,
    errors,
    geonode,
)
from ..db import models
from ..db.commands import surveyrelatedrecords as record_commands
from ..db.queries import surveyrelatedrecords as record_queries
from ..permissions import surveyrelatedrecords as record_permissions
from ..schemas import (
    events as event_schemas,
    identifiers,
    user as user_schemas,
)

logger = logging.getLogger(__name__)


def get_geonode_exportable_data_asset(
    record: models.SurveyRelatedRecord,
) -> models.RecordAsset | None:
    """Get the record's first data asset whose format GeoNode can import.

    Assets are sorted by name and id, so the same one is picked on every export.
    """
    return next(
        (
            asset
            for asset in sorted(record.assets, key=lambda a: (a.name, str(a.id)))
            if constants.AssetType.DATA in asset.asset_type
            and asset.relative_path is not None
            and pathlib.PurePath(asset.relative_path).suffix.lower()
            in constants.GEONODE_EXPORTABLE_DATA_ASSET_EXTENSIONS
        ),
        None,
    )


def is_exportable_to_geonode(
    record: models.SurveyRelatedRecord,
    settings: config.SeisLabDataSettings,
) -> bool:
    return all(
        (
            settings.target_geonode is not None,
            record.status == constants.SurveyRelatedRecordStatus.PUBLISHED,
            get_geonode_exportable_data_asset(record) is not None,
        )
    )


async def export_survey_related_record(
    *,
    request_id: identifiers.RequestId,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    initiator: user_schemas.User,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
    settings: config.SeisLabDataSettings,
) -> None:
    """Export a published record's data to GeoNode, along with its metadata.

    A record which was already exported has its GeoNode resource replaced,
    unless that resource is gone from GeoNode, in which case a new one is
    created. The record is held under export for the whole duration, which
    prevents modifying it meanwhile.
    """
    record_name = None
    try:
        if (
            record := await record_queries.get_survey_related_record(
                session, survey_related_record_id
            )
        ) is None:
            raise errors.SeisLabDataError(
                f"Survey-related record with id {survey_related_record_id} does not exist."
            )
        record_name = record.name
        if not record_permissions.can_export_survey_related_record(initiator, record):
            raise errors.UserNotAllowedError(
                "User is not allowed to export survey-related record."
            )
        if not is_exportable_to_geonode(record, settings):
            raise errors.SeisLabDataError(
                "Survey-related record cannot be exported to GeoNode - it must be "
                "published and have a data asset in a format supported by GeoNode."
            )
        archive_root = await Path(settings.readonly_archive_root_directory).resolve()
        data_path = await Path(
            archive_root,
            record.survey_mission.relative_path,
            get_geonode_exportable_data_asset(record).relative_path,
        ).resolve()
        # relative paths are user-editable, they must not be able to escape the archive
        if not data_path.is_relative_to(archive_root) or not await data_path.is_file():
            raise errors.SeisLabDataError(
                f"Data file of survey-related record not found at {str(data_path)!r}."
            )
        if not await record_commands.compare_and_set_survey_related_record_status(
            session,
            survey_related_record_id,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
            constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
        ):
            raise errors.SeisLabDataError(
                "Survey-related record changed status meanwhile - not exporting it."
            )
    # catching everything, as the user is waiting to hear how the export went -
    # these are background tasks, there is no one else to tell about errors
    except Exception as err:
        if not isinstance(err, errors.SeisLabDataError):
            logger.exception(f"Could not export record {survey_related_record_id}")
        await event_dispatcher(
            event_schemas.ExportEvent(
                initiator=initiator.id,
                request_id=request_id,
                resource_type=constants.ResourceType.RECORD,
                resource_id=str(survey_related_record_id),
                resource_name=record_name,
                stage=constants.ExportStage.ENDED,
                succeeded=False,
                details=str(err),
            )
        )
        return

    # pages showing the record learn of it being busy from its status change
    await event_dispatcher(
        event_schemas.ResourceStatusChangedEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.RECORD,
            resource_id=str(survey_related_record_id),
            resource_name=record_name,
            succeeded=True,
            new_status=constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
        )
    )
    await event_dispatcher(
        event_schemas.ExportEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.RECORD,
            resource_id=str(survey_related_record_id),
            resource_name=record_name,
            stage=constants.ExportStage.STARTED,
            succeeded=True,
        )
    )
    target = settings.target_geonode
    try:
        async with httpx.AsyncClient(base_url=target.url, timeout=30) as client:
            access_token = await geonode.get_access_token(
                client,
                username=target.username,
                password=target.password,
                client_id=target.client_id,
                client_secret=target.client_secret,
            )
            client.headers["Authorization"] = f"Bearer {access_token}"
            try:
                resource_pk = None
                if record.geonode_resource_url is not None and (
                    pk_match := re.search(r"/(\d+)/?$", record.geonode_resource_url)
                ):
                    existing = await client.get(
                        f"/api/v2/resources/{pk_match.group(1)}"
                    )
                    if existing.status_code == 404:
                        logger.info(
                            f"GeoNode resource {record.geonode_resource_url!r} no longer "
                            f"exists - exporting record as a new resource..."
                        )
                    else:
                        existing.raise_for_status()
                        resource_pk = int(pk_match.group(1))
                await event_dispatcher(
                    event_schemas.ExportEvent(
                        initiator=initiator.id,
                        request_id=request_id,
                        resource_type=constants.ResourceType.RECORD,
                        resource_id=str(survey_related_record_id),
                        resource_name=record_name,
                        stage=constants.ExportStage.PROGRESS,
                        succeeded=True,
                        details=f"Uploading {data_path.name!r} to GeoNode...",
                    )
                )
                execution_id = await geonode.upload_dataset(
                    client, await geonode.get_upload_files(data_path), resource_pk
                )
                execution = None
                async for execution in geonode.watch_execution(client, execution_id):
                    await event_dispatcher(
                        event_schemas.ExportEvent(
                            initiator=initiator.id,
                            request_id=request_id,
                            resource_type=constants.ResourceType.RECORD,
                            resource_id=str(survey_related_record_id),
                            resource_name=record_name,
                            stage=constants.ExportStage.PROGRESS,
                            succeeded=True,
                            details=f"GeoNode import is {execution['status']} "
                            f"({execution.get('step')})",
                        )
                    )
                resource_pk = execution["output_params"]["resources"][0]["id"]
                # metadata is set on every export, as replacing the data resets it
                record_url = (
                    f"{settings.public_url.rstrip('/')}/survey-related-records/"
                    f"{survey_related_record_id}"
                )
                metadata = {
                    "title": record.name,
                    "abstract": record.description or record.name,
                    "supplemental_information": (
                        f"Exported from seis-lab-data survey-related record: {record_url}"
                    ),
                    "temporal_extent_start": (
                        record.temporal_extent_begin.isoformat()
                        if record.temporal_extent_begin is not None
                        else None
                    ),
                    "temporal_extent_end": (
                        record.temporal_extent_end.isoformat()
                        if record.temporal_extent_end is not None
                        else None
                    ),
                }
                metadata_response = await client.patch(
                    f"/api/v2/resources/{resource_pk}", json=metadata
                )
                metadata_response.raise_for_status()
                resource_url = metadata_response.json()["resource"]["detail_url"]
            finally:
                # each export gets its own token, revoking it once done keeps
                # them from piling up in GeoNode - not worth failing the export for
                try:
                    revocation = await client.post(
                        "/o/revoke_token/",
                        data={"token": access_token, "token_type_hint": "access_token"},
                        auth=(target.client_id, target.client_secret),
                    )
                    revocation.raise_for_status()
                except httpx.HTTPError:
                    logger.warning(
                        "Could not revoke GeoNode access token", exc_info=True
                    )
        await record_commands.set_survey_related_record_geonode_export(
            session,
            survey_related_record_id,
            resource_url,
            dt.datetime.now(tz=dt.timezone.utc),
        )
    # catching everything, so the user is always told when the export failed
    except Exception as err:
        logger.exception(f"Could not export record {survey_related_record_id}")
        succeeded = False
        details = f"Could not export to GeoNode: {err}"
    else:
        succeeded = True
        details = resource_url
    finally:
        # conditional, so as not to undo a status which something else, such
        # as the unpublishing of the record's mission, has set meanwhile -
        # which has then announced the record's status change itself
        if await record_commands.compare_and_set_survey_related_record_status(
            session,
            survey_related_record_id,
            constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
        ):
            await event_dispatcher(
                event_schemas.ResourceStatusChangedEvent(
                    initiator=initiator.id,
                    request_id=request_id,
                    resource_type=constants.ResourceType.RECORD,
                    resource_id=str(survey_related_record_id),
                    resource_name=record_name,
                    succeeded=True,
                    new_status=constants.SurveyRelatedRecordStatus.PUBLISHED,
                )
            )
    await event_dispatcher(
        event_schemas.ExportEvent(
            initiator=initiator.id,
            request_id=request_id,
            resource_type=constants.ResourceType.RECORD,
            resource_id=str(survey_related_record_id),
            resource_name=record_name,
            stage=constants.ExportStage.ENDED,
            succeeded=succeeded,
            details=details,
        )
    )


async def recover_stale_geonode_exports(
    *,
    request_id: identifiers.RequestId,
    session: AsyncSession,
    event_dispatcher: dispatch.EventDispatcherProtocol,
) -> None:
    """Publish again the records whose export was abandoned by a dead worker."""
    # no permission check, unlike user-facing operations: this is system-initiated
    recovered = await record_commands.recover_stale_geonode_exports(
        session, dt.timedelta(seconds=constants.GEONODE_EXPORT_STALE_AFTER_SECONDS)
    )
    for record_id, record_name in recovered:
        logger.warning(f"Recovered survey-related record {record_id} from export")
        await event_dispatcher(
            event_schemas.ResourceStatusChangedEvent(
                initiator="system",
                request_id=request_id,
                resource_type=constants.ResourceType.RECORD,
                resource_id=str(record_id),
                resource_name=record_name,
                succeeded=True,
                new_status=constants.SurveyRelatedRecordStatus.PUBLISHED,
            )
        )
        await event_dispatcher(
            event_schemas.ExportEvent(
                initiator="system",
                request_id=request_id,
                resource_type=constants.ResourceType.RECORD,
                resource_id=str(record_id),
                resource_name=record_name,
                stage=constants.ExportStage.ENDED,
                succeeded=False,
                details="Export was abandoned - it did not finish in time",
            )
        )
