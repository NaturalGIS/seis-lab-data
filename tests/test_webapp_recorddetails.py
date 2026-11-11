"""Tests for keeping a record's detail page up to date without reloading it."""

import uuid

import pytest
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import (
    constants,
    subscribers,
)
from seis_lab_data.schemas import (
    identifiers,
    messages as message_schemas,
    user as user_schemas,
)
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend
from seis_lab_data.webapp.streamhandlers import common as common_handlers


@pytest.mark.integration
def test_details_component_is_morphed_into_the_detail_page(
    test_client: TestClient, published_sample_data
):
    record = published_sample_data["records"][0]
    request_id = uuid.uuid4()

    # anonymous, as published records' detail pages are public
    response = test_client.get(
        f"/survey-related-records/{record.id}/details/{request_id}"
    )

    assert response.status_code == 200
    assert "event: datastar-patch-elements" in response.text
    # matched by id and morphed, rather than replacing the content area, which
    # also holds the element that keeps the page's stream open
    assert "data: selector" not in response.text
    assert 'id="record-details"' in response.text


@pytest.mark.integration
def test_details_component_actions_report_to_the_page_stream(
    test_client: TestClient, published_sample_data, monkeypatch
):
    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), user_schemas.User(
            id=identifiers.UserId("some-editor"),
            email="editor@example.com",
            username="editor",
            roles=[constants.ROLE_EDITOR],
            active=True,
        )

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)
    record = published_sample_data["records"][0]
    request_id = uuid.uuid4()

    response = test_client.get(
        f"/survey-related-records/{record.id}/details/{request_id}"
    )

    assert response.status_code == 200
    # the page's own request id, which its stream filters progress messages by
    assert f"request_id={request_id}" in response.text


@pytest.mark.integration
def test_details_component_needs_a_valid_request_id(
    test_client: TestClient, published_sample_data
):
    record = published_sample_data["records"][0]

    response = test_client.get(f"/survey-related-records/{record.id}/details/nope")

    assert response.status_code == 400


async def _handle_export(stage, succeeded, resource_id="the-record"):
    message = message_schemas.ExportMessage(
        resource_type=constants.ResourceType.RECORD,
        resource_id=resource_id,
        request_id=uuid.uuid4(),
        stage=stage,
        succeeded=succeeded,
        details="http://geonode.test/catalogue/#/dataset/8",
    )
    context = subscribers.HandlerContext(resource_id="the-record")
    return [
        event
        async for event in common_handlers.handle_export_detail_page(message, context)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "succeeded, expected_category",
    [
        pytest.param(True, "success", id="succeeded"),
        pytest.param(False, "danger", id="failed"),
    ],
)
async def test_export_outcome_is_notified(succeeded, expected_category):
    events = await _handle_export(constants.ExportStage.ENDED, succeeded)

    # only notified - the details are re-fetched as the record's status changes
    assert len(events) == 1
    assert "showFlash(" in events[0]
    assert f'"category": "{expected_category}"' in events[0]


@pytest.mark.asyncio
async def test_export_start_is_left_to_the_status_change():
    assert await _handle_export(constants.ExportStage.STARTED, True) == []


@pytest.mark.asyncio
async def test_export_progress_only_notifies():
    events = await _handle_export(constants.ExportStage.PROGRESS, True)

    assert len(events) == 1
    assert "showFlash(" in events[0]


@pytest.mark.asyncio
async def test_export_of_another_record_is_ignored():
    assert await _handle_export(constants.ExportStage.ENDED, True, "other") == []
