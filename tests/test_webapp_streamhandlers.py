"""Tests for the handlers relaying item status changes to the pages that show them."""

import uuid

import pytest

from seis_lab_data import (
    constants,
    subscribers,
)
from seis_lab_data.schemas import messages as message_schemas
from seis_lab_data.webapp.streamhandlers import common as common_handlers

# how the flash helpers show a notification right away, or store it for the next page
_SAME_PAGE_NOTIFICATION = "showFlash("
_STORED_NOTIFICATION = "localStorage.setItem('sld:flash'"


def _status_changed(resource_type, resource_id, succeeded=True):
    return message_schemas.ResourceStatusChangedMessage(
        request_id=uuid.uuid4(),
        resource_type=resource_type,
        resource_id=str(resource_id),
        succeeded=succeeded,
        new_status=constants.SurveyRelatedRecordStatus.PUBLISHED.value,
    )


async def _collect(handler, message, context) -> list[str]:
    return [event async for event in handler(message, context)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "succeeded, expected_refreshes",
    [pytest.param(True, 1, id="succeeded"), pytest.param(False, 0, id="failed")],
)
async def test_list_page_quietly_refreshes_on_status_change(
    succeeded, expected_refreshes
):
    events = await _collect(
        common_handlers.handle_resource_status_changed_list_page,
        _status_changed(constants.ResourceType.RECORD, uuid.uuid4(), succeeded),
        subscribers.HandlerContext(),
    )

    assert len(events) == expected_refreshes
    assert all("listingVersion" in event for event in events)
    assert not any(_SAME_PAGE_NOTIFICATION in event for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "own_record, expected_refreshes",
    [pytest.param(True, 1, id="own-record"), pytest.param(False, 0, id="other-record")],
)
async def test_mission_page_refreshes_only_for_its_own_records(
    db_session_maker,
    sample_survey_related_records,
    sample_survey_missions,
    admin_user,
    own_record,
    expected_refreshes,
):
    record = sample_survey_related_records[0]
    mission_id = (
        record.survey_mission_id
        if own_record
        else next(
            m.id for m in sample_survey_missions if m.id != record.survey_mission_id
        )
    )

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.RECORD, record.id),
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
            db_session_factory=db_session_maker,
            user=admin_user,
        ),
    )

    assert sum("listingVersion" in event for event in events) == expected_refreshes
    # the page is not reloaded, a notification stored for the next one would be
    # shown out of context, on whatever page the user visits next
    assert not any(_STORED_NOTIFICATION in event for event in events)


@pytest.mark.asyncio
async def test_record_page_refreshes_its_details_on_status_change():
    record_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.RECORD, record_id),
        subscribers.HandlerContext(
            resource_id=str(record_id),
            resource_type=constants.ResourceType.RECORD,
        ),
    )

    # no reload: notified on the same page, whose details are then re-fetched
    assert len(events) == 2
    assert _SAME_PAGE_NOTIFICATION in events[0]
    assert "detailsVersion" in events[1]


@pytest.mark.asyncio
async def test_status_change_notification_is_stored_for_the_reloaded_page():
    mission_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(constants.ResourceType.MISSION, mission_id),
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
            url_resolver=lambda name, **params: f"/{name}/{params}",
        ),
    )

    assert _STORED_NOTIFICATION in events[0]
    assert "window.location" in events[-1]
