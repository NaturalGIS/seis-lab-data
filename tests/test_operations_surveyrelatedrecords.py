"""Survey-related record operations

Access to survey-related records and their preview images depends on their publication
status, and editors can update many records at once by filtering or selecting them. A
record cannot be edited while a background task is working on it.
"""

import uuid

import pytest

from seis_lab_data import (
    constants,
    errors,
)
from seis_lab_data.db.commands import recordassets as asset_commands
from seis_lab_data.db.commands import surveymissions as mission_commands
from seis_lab_data.db.commands import surveyrelatedrecords as record_commands
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.operations import surveyrelatedrecords as record_ops
from seis_lab_data.schemas import events as event_schemas
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import surveyrelatedrecords as record_schemas
from seis_lab_data.schemas.identifiers import (
    RequestId,
    UserId,
)
from seis_lab_data.schemas.user import User


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_published_record_gives_anonymous_visitors_its_derived_asset_data(
    db,
    db_session_maker,
    sample_survey_related_records,
):
    """Visitors who are not logged in can obtain the preview images of a published
    survey-related record.
    """
    # this is what the record asset data endpoint relies on in order to serve
    # previews of published records to visitors who are not logged in
    record = sample_survey_related_records[0]
    preview_id = identifiers.RecordAssetId(uuid.uuid4())
    async with db_session_maker() as session:
        await asset_commands.replace_derived_record_assets(
            session,
            record,
            [
                record_schemas.DerivedRecordAssetCreate(
                    id=preview_id,
                    name="A preview",
                    media_type="image/webp",
                    asset_type=[
                        constants.AssetType.THUMBNAIL,
                        constants.AssetType.PREVIEW,
                    ],
                    data=b"not a webp",
                )
            ],
        )
        # sample records are created as drafts
        await record_commands.set_survey_related_record_status(
            session,
            identifiers.SurveyRelatedRecordId(record.id),
            constants.SurveyRelatedRecordStatus.PUBLISHED,
        )
        found, _related_to, _subject_for = await record_ops.get_survey_related_record(
            identifiers.SurveyRelatedRecordId(record.id), None, session
        )
    assert [a.data for a in found.assets if a.id == preview_id] == [b"not a webp"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_draft_record_denies_anonymous_visitors_its_derived_asset_data(
    db,
    db_session_maker,
    sample_survey_related_records,
):
    """Visitors who are not logged in cannot access a draft survey-related record, and
    therefore cannot obtain its preview images either.
    """
    # the record asset data endpoint turns this error into a 404, so that a
    # draft record's previews are not even known to exist
    record = sample_survey_related_records[0]
    async with db_session_maker() as session:
        with pytest.raises(errors.UserNotAllowedError):
            await record_ops.get_survey_related_record(
                identifiers.SurveyRelatedRecordId(record.id), None, session
            )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_denies_user_without_editor_role(
    db,
    db_session_maker,
    sample_survey_related_records,
):
    """A user without an editing role cannot update survey-related records in bulk, and
    the attempt is reported as failed.
    """
    plain_user = User(
        id=UserId("plain-user"), username="plain", email="plain@tests.dev", roles=[]
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=record_schemas.SurveyRelatedRecordBulkUpdate(),
            initiator=plain_user,
            session=session,
            event_dispatcher=dispatcher,
            name_filter="First",
        )
    assert result is None
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_workflow_stage_filter_excludes_non_matching_records(
    db,
    db_session_maker,
    sample_survey_related_records,
    bootstrap_workflow_stages,
    admin_user,
):
    """A bulk update restricted to a workflow stage changes no records when none of them
    is in that workflow stage.
    """
    # sample records are all in the "raw data" workflow stage, not this one
    non_matching_stage = next(
        w for w in bootstrap_workflow_stages if w.name == "quality control data"
    )
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        description="Should not apply"
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=to_update,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
            workflow_stage_id=identifiers.WorkflowStageId(non_matching_stage.id),
        )
    assert result == 0
    assert dispatcher.events[0].succeeded is True
    assert dispatcher.events[0].affected_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_dataset_category_filter_combines_with_name_filter(
    db,
    db_session_maker,
    sample_survey_related_records,
    bootstrap_dataset_categories,
    admin_user,
):
    """A bulk update restricted to both a dataset category and a name changes only the
    records that match both.
    """
    # both sample records are in "bathymetry", so this narrows only via name_filter
    matching_category = next(
        c for c in bootstrap_dataset_categories if c.name == "bathymetry"
    )
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(description="Should apply")
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=to_update,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
            name_filter="First",
            dataset_category_id=identifiers.DatasetCategoryId(matching_category.id),
        )
    assert result == 1
    assert dispatcher.events[0].succeeded is True
    assert dispatcher.events[0].affected_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_asset_media_type_filter_excludes_non_matching_records(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
):
    """A bulk update restricted to records having assets of a given media type changes
    no records when none of them has such assets.
    """
    # sample record assets declare application/octet-stream as their media type,
    # so this filter matches none of them
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        description="Should not apply"
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=to_update,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
            name_filter="First",
            asset_media_type_filter="video/mp4",
        )
    assert result == 0
    assert dispatcher.events[0].succeeded is True
    assert dispatcher.events[0].affected_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_manually_selected_records_via_operation(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
):
    """A bulk update applied to a manual selection of records changes exactly the
    selected records, and the number of changed records is reported.
    """
    _first_record, second_record = sample_survey_related_records
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        description="Bulk-updated via operation"
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=to_update,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
            selected=[identifiers.SurveyRelatedRecordId(second_record.id)],
        )
    assert result == 1
    assert dispatcher.events[0].succeeded is True
    assert dispatcher.events[0].affected_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_invalidates_and_unpublishes_records_missing_required_fields(
    db,
    db_session_maker,
    published_sample_data,
    admin_user,
):
    """A bulk update which removes the dataset category of published survey-related
    records marks them as invalid, reports the missing dataset category and withdraws
    them from publication.
    """
    _first_record, second_record = published_sample_data["records"]
    record_id = identifiers.SurveyRelatedRecordId(second_record.id)
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=record_schemas.SurveyRelatedRecordBulkUpdate(
                dataset_category_id=None
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
            selected=[record_id],
        )
    async with db_session_maker() as session:
        record = await record_queries.get_survey_related_record(session, record_id)
    assert result == 1
    assert record.validation_result["is_valid"] is False
    assert [e["name"] for e in record.validation_result["errors"]] == [
        "dataset_category_id"
    ]
    assert record.status == constants.SurveyRelatedRecordStatus.DRAFT


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mission_status, expected_record_status",
    [
        pytest.param(
            constants.SurveyMissionStatus.PUBLISHED,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
            id="published-mission",
        ),
        pytest.param(
            constants.SurveyMissionStatus.DRAFT,
            constants.SurveyRelatedRecordStatus.DRAFT,
            id="draft-mission",
        ),
    ],
)
async def test_bulk_update_validates_records_which_become_complete(
    db,
    db_session_maker,
    sample_survey_related_records,
    bootstrap_dataset_categories,
    admin_user,
    mission_status,
    expected_record_status,
):
    """A bulk update which provides the missing dataset category of invalid draft
    survey-related records marks them as valid, and publishes them only when their
    survey mission is published.
    """
    _first_record, second_record = sample_survey_related_records
    record_id = identifiers.SurveyRelatedRecordId(second_record.id)
    category = next(c for c in bootstrap_dataset_categories if c.name == "bathymetry")
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session,
            identifiers.SurveyMissionId(second_record.survey_mission_id),
            mission_status,
        )
        await record_commands.bulk_update_manually_selected_records(
            session,
            record_schemas.SurveyRelatedRecordBulkUpdate(dataset_category_id=None),
            [record_id],
        )
        await record_commands.update_survey_related_record_validation_result(
            session,
            await record_queries.get_survey_related_record(session, record_id),
            validation_result={
                "is_valid": False,
                "errors": [
                    {
                        "name": "dataset_category_id",
                        "message": "Input should be a valid UUID",
                        "type_": "uuid_type",
                    }
                ],
            },
        )
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=record_schemas.SurveyRelatedRecordBulkUpdate(
                dataset_category_id=identifiers.DatasetCategoryId(category.id)
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
            selected=[record_id],
        )
    async with db_session_maker() as session:
        record = await record_queries.get_survey_related_record(session, record_id)
    assert result == 1
    assert record.validation_result == {"is_valid": True, "errors": None}
    assert record.status == expected_record_status


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_refuses_record_under_derivation(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
):
    """A survey-related record cannot be updated while its previews are being generated,
    and the attempt is reported as failed.
    """
    first_record, _ = sample_survey_related_records
    record_id = identifiers.SurveyRelatedRecordId(first_record.id)
    async with db_session_maker() as session:
        await record_commands.set_survey_related_record_status(
            session, record_id, constants.SurveyRelatedRecordStatus.UNDER_DERIVATION
        )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        with pytest.raises(errors.SeisLabDataError):
            await record_ops.update_survey_related_record(
                request_id=RequestId(uuid.uuid4()),
                survey_related_record_id=record_id,
                to_update=record_schemas.SurveyRelatedRecordUpdate(
                    description="Should not apply"
                ),
                initiator=admin_user,
                session=session,
                event_dispatcher=dispatcher,
            )
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0].succeeded is False
