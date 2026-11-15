"""Tests for a record's detail page, also kept up to date without reloading it."""

import uuid

import pytest
import sqlmodel
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import (
    constants,
    subscribers,
)
from seis_lab_data.db import models
from seis_lab_data.schemas import (
    identifiers,
    messages as message_schemas,
    user as user_schemas,
)
from seis_lab_data.webapp import jinjafilters
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend
from seis_lab_data.webapp.streamhandlers import common as common_handlers


@pytest.mark.integration
def test_detail_page_shows_the_discovery_info(
    test_client: TestClient, published_sample_data, sync_db_engine
):
    record = published_sample_data["records"][0]
    with sqlmodel.Session(sync_db_engine) as session:
        db_record = session.get(models.SurveyRelatedRecord, record.id)
        db_record.discovery_info = {
            "file_size_bytes": 1_500_000,
            "nodata": -3.4028234663852886e38,
        }
        session.add(db_record)
        session.commit()

    response = test_client.get(f"/survey-related-records/{record.id}")

    assert response.status_code == 200
    # the values only, as the shown names depend on the compiled translations
    assert "1.5 MB" in response.text
    # JSONB gives the Float32 nodata back as a 39-digit integer
    assert "-3.40282e+38" in response.text


def test_discovery_info_items_are_ordered_and_formatted():
    items = jinjafilters.get_discovery_info_items(
        {
            "coverage": "partial",
            "duration_seconds": 1803.25,
            "echo_sounder_id": 712,
            "point_count_estimated": True,
            "point_count": 8400000,
            "nodata": -9999.0,
            "pixel_size_y": -10.0,
            "pixel_size_x": 10.0,
            "height": 11715,
            "width": 5258,
            "bbox_native": [1.5, 2, 3.25, 4],
            "crs_from_mission": True,
            "epsg": 3763,
            "crs_name": "ETRS89 / Portugal TM06",
            "driver": "XYZ",
            "type": "raster",
            "file_size_bytes": 1_500_000,
        }
    )

    # the type and the coverage are stored without being shown
    assert [(str(name), str(value)) for name, value in items] == [
        ("File size", "1.5 MB"),
        ("Format", "XYZ"),
        ("CRS", "ETRS89 / Portugal TM06 - EPSG:3763 (from the survey mission)"),
        ("Native bounding box", "1.5, 2, 3.25, 4"),
        ("Size (px)", "5258 x 11715"),
        ("Pixel size (CRS units)", "10 x 10"),
        ("Nodata value", "-9999"),
        ("Points", "8400000 (estimated)"),
        ("Echo sounder", "EM 712"),
        ("Duration", "30 min"),
    ]
    # a CRS declared by the file, and an exact point count
    assert jinjafilters.get_discovery_info_items(
        {"crs_name": "WGS 84", "epsg": 4326, "point_count": 4}
    ) == [("CRS", "WGS 84 - EPSG:4326"), ("Points", "4")]
    # a pixel size in degrees, as stored for a raster in a geographic CRS
    assert jinjafilters.get_discovery_info_items(
        {"pixel_size_x": 3.60174e-05, "pixel_size_y": -3.60174e-05}
    ) == [("Pixel size (CRS units)", "0.0000360174 x 0.0000360174")]
    assert jinjafilters.get_discovery_info_items({"duration_seconds": 25.0}) == [
        ("Duration", "25 s")
    ]
    # a key without a name of its own would be shown as it is stored
    assert all(
        str(key.get_translated_value()) != key.value
        for key in constants.DiscoveryInfoKey
    )


@pytest.mark.parametrize("discovery_info", [None, {}])
def test_discovery_info_items_of_a_record_without_any(discovery_info):
    assert jinjafilters.get_discovery_info_items(discovery_info) == []


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
def test_details_component_shows_the_full_path_of_data_assets(
    test_client: TestClient, published_sample_data, settings, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "readonly_archive_root_directory", tmp_path)
    record = published_sample_data["records"][0]
    mission = next(
        m for m in published_sample_data["missions"] if m.id == record.survey_mission_id
    )
    asset = next(a for a in record.assets if constants.AssetType.DATA in a.asset_type)

    response = test_client.get(
        f"/survey-related-records/{record.id}/details/{uuid.uuid4()}"
    )

    assert response.status_code == 200
    assert str(tmp_path / mission.relative_path / asset.relative_path) in response.text


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
