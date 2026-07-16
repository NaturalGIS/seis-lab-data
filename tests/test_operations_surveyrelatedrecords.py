import uuid

import pytest

from seis_lab_data import constants
from seis_lab_data.operations import surveyrelatedrecords as record_ops
from seis_lab_data.schemas import (
    identifiers,
    surveyrelatedrecords as record_schemas,
    common as common_schemas,
    events as event_schemas,
)
from seis_lab_data.schemas.user import User
from seis_lab_data.schemas.identifiers import UserId, RequestId


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_denies_user_without_editor_role(
    db,
    db_session_maker,
    sample_survey_related_records,
):
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
            en_name_filter="First",
        )
    assert result is None
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_restricts_non_admin_editor_to_owned_records(
    db,
    db_session_maker,
    sample_survey_related_records,
    bootstrap_workflow_stages,
):
    # this editor owns none of the sample records/missions/projects
    other_editor = User(
        id=UserId("other-editor"),
        username="other-editor",
        email="other-editor@tests.dev",
        roles=[constants.ROLE_EDITOR],
    )
    new_stage = [
        w for w in bootstrap_workflow_stages if w.name["en"] == "quality control data"
    ][0]
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        workflow_stage_id=identifiers.WorkflowStageId(new_stage.id)
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=to_update,
            initiator=other_editor,
            session=session,
            event_dispatcher=dispatcher,
            en_name_filter="First",
        )
    assert result == 0
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0].succeeded is True
    assert dispatcher.events[0].affected_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_admin_bypasses_ownership_restriction(
    db,
    db_session_maker,
    sample_survey_related_records,
    bootstrap_workflow_stages,
    admin_user,
):
    first_record, second_record = sample_survey_related_records
    new_stage = [
        w for w in bootstrap_workflow_stages if w.name["en"] == "quality control data"
    ][0]
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        workflow_stage_id=identifiers.WorkflowStageId(new_stage.id)
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        result = await record_ops.bulk_update_survey_related_records(
            request_id=RequestId(uuid.uuid4()),
            to_update=to_update,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
            en_name_filter="First",
        )
    assert result == 1
    assert dispatcher.events[0].succeeded is True
    assert dispatcher.events[0].affected_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_update_manually_selected_records_via_operation(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
):
    first_record, second_record = sample_survey_related_records
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        description=common_schemas.LocalizableDraftDescription(
            en="Bulk-updated via operation"
        )
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
