import itertools
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...constants import SurveyRelatedRecordStatus
from ...schemas import (
    identifiers,
    surveyrelatedrecords as record_schemas,
)
from .. import models
from ..queries import surveyrelatedrecords as record_queries
from .common import get_bbox_4326_for_db

logger = logging.getLogger(__name__)


async def create_survey_related_record(
    session: AsyncSession,
    to_create: record_schemas.SurveyRelatedRecordCreate,
) -> models.SurveyRelatedRecord:
    survey_record = models.SurveyRelatedRecord(
        **to_create.model_dump(exclude={"assets", "bbox_4326", "related_records"}),
        bbox_4326=(
            get_bbox_4326_for_db(bbox)
            if (bbox := to_create.bbox_4326) is not None
            else bbox
        ),
    )
    # need to ensure english name is unique for combination of mission and record
    if await record_queries.get_survey_related_record_by_english_name(
        session,
        identifiers.SurveyMissionId(to_create.survey_mission_id),
        to_create.name.en,
    ):
        raise errors.SeisLabDataError(
            f"There is already a survey-related record with english name {to_create.name.en!r} for "
            f"the same survey mission."
        )
    session.add(survey_record)
    for asset_to_create in to_create.assets:
        db_asset = models.RecordAsset(
            **asset_to_create.model_dump(),
            survey_related_record_id=survey_record.id,
        )
        session.add(db_asset)
    for related in to_create.related_records:
        db_related = models.SurveyRelatedRecordSelfLink(
            subject_id=survey_record.id,
            related_to_id=related.related_record_id,
            relation=related.relationship.model_dump(),
        )
        session.add(db_related)
    await session.commit()
    await session.refresh(survey_record)
    return await record_queries.get_survey_related_record(session, to_create.id)


async def delete_survey_related_record(
    session: AsyncSession,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
) -> None:
    if survey_record := (
        await record_queries.get_survey_related_record(
            session, survey_related_record_id
        )
    ):
        await session.delete(survey_record)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id!r} does not exist."
        )


async def bulk_update_manually_selected_records(
    session: AsyncSession,
    to_update: record_schemas.SurveyRelatedRecordBulkUpdate,
    selected: list[identifiers.SurveyRelatedRecordId],
    user_id: identifiers.UserId,
):
    raise NotImplementedError


async def bulk_update_filtered_records(
    session: AsyncSession,
    to_update: record_schemas.SurveyRelatedRecordBulkUpdate,
    user_id: identifiers.UserId,
    excluded_record_ids: list[identifiers.SurveyRelatedRecordId] | None = None,
    selection_query_filters: dict[str, str] | None = None,
) -> int:
    page_size = 1_000
    updated_count = 0
    for current_page in itertools.count(start=1):
        (
            paginated_records,
            total,
        ) = await record_queries.list_accessible_survey_related_records(
            session,
            user_id,
            page=current_page,
            page_size=page_size,
            include_total=True,
            en_name_filter=selection_query_filters.get("en_name_filter"),
            pt_name_filter=selection_query_filters.get("pt_name_filter"),
            spatial_intersect=selection_query_filters.get("spatial_intersect"),
            temporal_extent=selection_query_filters.get("temporal_extent"),
            asset_path_fragment_filter=selection_query_filters.get(
                "asset_path_fragment_filter"
            ),
        )
        for rec in paginated_records:
            if identifiers.SurveyRelatedRecordId(rec.id) in (excluded_record_ids or []):
                logger.debug(f"ignoring record {rec.id!r}...")
                continue
            for key, value in to_update.model_dump(
                exclude={"bbox_4326", "related_records"},
                exclude_unset=True,
            ):
                setattr(rec, key, value)
            updated_bbox_4326 = (
                get_bbox_4326_for_db(bbox)
                if (bbox := to_update.bbox_4326) is not None
                else None
            )
            rec.bbox_4326 = updated_bbox_4326
            session.add(rec)
            updated_count += 1
        if current_page * page_size >= total:
            break
    try:
        await session.commit()
    except Exception as err:
        await session.rollback()
        raise err
    return updated_count


async def update_survey_related_record(
    session: AsyncSession,
    survey_related_record: models.SurveyRelatedRecord,
    to_update: record_schemas.SurveyRelatedRecordUpdate,
):
    """Update a survey-related record and its assets.

    Updating the record also means that underlying assets may be
    added, updated, or removed.
    """
    logger.debug(f"{to_update=}")
    for key, value in to_update.model_dump(
        exclude={"bbox_4326", "assets", "related_records"}, exclude_unset=True
    ).items():
        setattr(survey_related_record, key, value)
    updated_bbox_4326 = (
        get_bbox_4326_for_db(bbox)
        if (bbox := to_update.bbox_4326) is not None
        else None
    )
    survey_related_record.bbox_4326 = updated_bbox_4326
    session.add(survey_related_record)

    for proposed_asset in to_update.assets:
        try:
            existing_asset = [
                a
                for a in survey_related_record.assets
                if identifiers.RecordAssetId(a.id) == proposed_asset.id
            ][0]
        except IndexError:  # this is a new asset that needs to be created
            db_asset = models.RecordAsset(
                **proposed_asset.model_dump(),
                survey_related_record_id=survey_related_record.id,
            )
            session.add(db_asset)
        else:  # this is an existing asset that needs to be updated
            for key, value in proposed_asset.model_dump(exclude_unset=True).items():
                setattr(existing_asset, key, value)
            session.add(existing_asset)

    proposed_asset_ids = [s.id for s in to_update.assets]
    for existing_asset in survey_related_record.assets:
        if identifiers.RecordAssetId(existing_asset.id) not in proposed_asset_ids:
            await session.delete(existing_asset)

    already_related_to = (
        await record_queries.list_survey_related_record_related_to_records(
            session, identifiers.SurveyRelatedRecordId(survey_related_record.id)
        )
    )
    logger.debug(f"{already_related_to=}")
    for proposed_related_to in to_update.related_records:
        # did a relationship to this record already exist?
        try:
            existing_relationship = [
                r
                for r in survey_related_record.related_to_links
                if r.related_to_id == proposed_related_to.related_record_id
            ][0]
        except IndexError:  # this is a new relationship that must be created
            db_relationship = models.SurveyRelatedRecordSelfLink(
                subject_id=survey_related_record.id,
                related_to_id=proposed_related_to.related_record_id,
                relation=proposed_related_to.relationship.model_dump(),
            )
            session.add(db_relationship)
        else:  # this is an existing relationship that needs to be updated
            existing_relationship.relation = (
                proposed_related_to.relationship.model_dump()
            )
            session.add(existing_relationship)

    proposed_related_to_ids = [r.related_record_id for r in to_update.related_records]
    for existing_related in survey_related_record.related_to_links:
        if (
            identifiers.SurveyRelatedRecordId(existing_related.related_to_id)
            not in proposed_related_to_ids
        ):
            await session.delete(existing_related)

    await session.commit()
    await session.refresh(survey_related_record)
    return await record_queries.get_survey_related_record(
        session, identifiers.SurveyRelatedRecordId(survey_related_record.id)
    )


async def update_survey_related_record_validation_result(
    session: AsyncSession,
    survey_related_record: models.SurveyRelatedRecord,
    validation_result: models.ValidationResult,
) -> models.SurveyRelatedRecord:
    """Unconditionally sets the survey-related record's validation result."""
    survey_related_record.validation_result = validation_result
    session.add(survey_related_record)
    await session.commit()
    await session.refresh(survey_related_record)
    return await record_queries.get_survey_related_record(
        session, identifiers.SurveyRelatedRecordId(survey_related_record.id)
    )


async def set_survey_related_record_status(
    session: AsyncSession,
    survey_related_record_id: identifiers.SurveyRelatedRecordId,
    status: SurveyRelatedRecordStatus,
) -> models.SurveyRelatedRecord:
    """Unconditionally sets the survey-related record's status."""
    if (
        survey_related_record := (
            await record_queries.get_survey_related_record(
                session, survey_related_record_id
            )
        )
    ) is None:
        raise errors.SeisLabDataError(
            f"Survey-related record with id {survey_related_record_id} does not exist."
        )
    survey_related_record.status = status
    session.add(survey_related_record)
    await session.commit()
    await session.refresh(survey_related_record)
    return await record_queries.get_survey_related_record(
        session, identifiers.SurveyRelatedRecordId(survey_related_record_id)
    )
