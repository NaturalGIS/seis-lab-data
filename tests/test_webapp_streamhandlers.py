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
@pytest.mark.parametrize(
    "own_mission, expected_refreshes",
    [pytest.param(True, 1, id="own-mission"), pytest.param(False, 0, id="other")],
)
async def test_record_page_refreshes_its_details_on_its_mission_status_change(
    own_mission, expected_refreshes
):
    mission_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        _status_changed(
            constants.ResourceType.MISSION, mission_id if own_mission else uuid.uuid4()
        ),
        subscribers.HandlerContext(
            resource_id=str(uuid.uuid4()),
            parent_resource_id=str(mission_id),
            resource_type=constants.ResourceType.RECORD,
        ),
    )

    assert len(events) == expected_refreshes
    assert all("detailsVersion" in event for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_status, resets_progress",
    [
        pytest.param(constants.SurveyMissionStatus.PUBLISHED, False, id="published"),
        pytest.param(
            constants.SurveyMissionStatus.UNDER_DISCOVERY, True, id="under-discovery"
        ),
    ],
)
async def test_mission_page_refreshes_in_place_on_status_change(
    new_status, resets_progress
):
    mission_id = uuid.uuid4()
    message = message_schemas.ResourceStatusChangedMessage(
        request_id=uuid.uuid4(),
        resource_type=constants.ResourceType.MISSION,
        resource_id=str(mission_id),
        succeeded=True,
        new_status=new_status.value,
    )

    events = await _collect(
        common_handlers.handle_resource_status_changed_detail_page,
        message,
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
        ),
    )

    # a reload would close the page's stream and lose the messages sent meanwhile
    assert len(events) == 2
    assert _SAME_PAGE_NOTIFICATION in events[0]
    assert not any("window.location" in event for event in events)
    for signal in ("status", "detailsVersion", "listingVersion"):
        assert signal in events[1]
    assert new_status.value in events[1]
    assert ("discoveryProgress" in events[1]) is resets_progress


def _discovery(mission_id, modification, succeeded=True, details=None, request_id=None):
    return message_schemas.DiscoveryMessage(
        request_id=request_id or uuid.uuid4(),
        resource_type=constants.ResourceType.MISSION,
        resource_id=str(mission_id),
        modification=modification,
        succeeded=succeeded,
        details=details,
    )


@pytest.mark.asyncio
async def test_mission_page_shows_discovery_progress_in_place():
    mission_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_discovery_detail_page,
        _discovery(mission_id, constants.DiscoveryStage.PROGRESS, details="3 files"),
        subscribers.HandlerContext(
            resource_id=str(mission_id), resource_type=constants.ResourceType.MISSION
        ),
    )

    assert len(events) == 1
    assert "discoveryProgress" in events[0] and "3 files" in events[0]
    assert "listingVersion" in events[0]
    assert _SAME_PAGE_NOTIFICATION not in events[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modification, own_request, expected_notifications",
    [
        pytest.param(constants.DiscoveryStage.ENDED, False, 1, id="ended"),
        pytest.param(
            constants.DiscoveryStage.CANCELLED, True, 1, id="cancel failed, own"
        ),
        pytest.param(
            constants.DiscoveryStage.CANCELLED, False, 0, id="cancel failed, other"
        ),
    ],
)
async def test_mission_page_discovery_failure_notifications(
    modification, own_request, expected_notifications
):
    mission_id = uuid.uuid4()
    request_id = uuid.uuid4()

    events = await _collect(
        common_handlers.handle_discovery_detail_page,
        _discovery(
            mission_id,
            modification,
            succeeded=False,
            details="reason",
            request_id=request_id if own_request else None,
        ),
        subscribers.HandlerContext(
            resource_id=str(mission_id),
            resource_type=constants.ResourceType.MISSION,
            request_id=request_id,
        ),
    )

    assert (
        sum(_SAME_PAGE_NOTIFICATION in event for event in events)
        == expected_notifications
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource_type, own_item, expected",
    [
        pytest.param(
            constants.ResourceType.MISSION, True, "listingVersion", id="mission"
        ),
        pytest.param(constants.ResourceType.MISSION, False, None, id="other mission"),
        pytest.param(constants.ResourceType.RECORD, True, "/detail", id="record"),
        pytest.param(constants.ResourceType.RECORD, False, None, id="other record"),
    ],
)
async def test_detail_pages_refresh_on_derivation(resource_type, own_item, expected):
    record_id = uuid.uuid4()
    mission_id = uuid.uuid4()
    context_resource_id = (
        record_id if resource_type == constants.ResourceType.RECORD else mission_id
    )

    events = await _collect(
        common_handlers.handle_derivation_detail_page,
        message_schemas.DerivationMessage(
            request_id=uuid.uuid4(),
            resource_type=constants.ResourceType.RECORD,
            resource_id=str(record_id),
            parent_resource_id=str(mission_id),
        ),
        subscribers.HandlerContext(
            resource_id=str(context_resource_id if own_item else uuid.uuid4()),
            resource_type=resource_type,
            url_resolver=lambda name, **params: f"/{name.split(':')[1]}",
        ),
    )

    if expected is None:
        assert events == []
    else:
        assert len(events) == 1 and expected in events[0]
        assert _SAME_PAGE_NOTIFICATION not in events[0]
