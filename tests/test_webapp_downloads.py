"""Asset downloads

The data files of survey-related records can be downloaded individually, or through a
list of download links covering a selection of records, subject to the same visibility
rules as the catalog.
"""

import io
import json
import os
import urllib.parse
import zipfile

import pytest
import sqlmodel
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import user as user_schemas
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration

_FILE_CONTENTS = b"0123456789abcdefghij"


@pytest.fixture
def archive_root(settings, monkeypatch, tmp_path):
    """Set the read-only archive root to a temporary directory and return it."""
    monkeypatch.setattr(settings, "readonly_archive_root_directory", tmp_path)
    return tmp_path


@pytest.fixture
def logged_in(monkeypatch):
    """Authenticate every request as a user without roles."""

    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), user_schemas.User(
            id=identifiers.UserId("some-user"),
            email="user@example.com",
            username="user",
            roles=[],
            active=True,
        )

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


@pytest.fixture
def create_asset(sync_db_engine, archive_root, sample_survey_missions):
    """Provide a factory of data assets for a record, optionally writing their file in
    the archive.
    """
    missions = {m.id: m for m in sample_survey_missions}

    def _create(
        record: models.SurveyRelatedRecord,
        relative_path: str | None = "some/dir/file.xyz",
        asset_type: list[constants.AssetType] | None = None,
        write_file: bool = True,
    ) -> models.RecordAsset:
        if write_file:
            file_path = (
                archive_root
                / missions[record.survey_mission_id].relative_path
                / relative_path
            )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(_FILE_CONTENTS)
        asset = models.RecordAsset(
            name="a data file",
            survey_related_record_id=record.id,
            relative_path=relative_path,
            media_type="text/plain",
            asset_type=asset_type or [constants.AssetType.DATA],
        )
        with sqlmodel.Session(sync_db_engine) as session:
            session.add(asset)
            session.commit()
            session.refresh(asset)
        return asset

    return _create


def _download_url(asset: models.RecordAsset) -> str:
    return (
        f"/survey-related-records/{asset.survey_related_record_id}"
        f"/assets/{asset.id}/download"
    )


def test_download_published_record_asset_anonymously(
    test_client: TestClient, published_sample_data, create_asset
):
    """An anonymous visitor can download a data file of a published survey-related
    record, which arrives with its original file name and content type.
    """
    asset = create_asset(published_sample_data["records"][0])
    response = test_client.get(_download_url(asset))
    assert response.status_code == 200
    assert response.content == _FILE_CONTENTS
    assert response.headers["content-type"].startswith("text/plain")
    assert 'filename="file.xyz"' in response.headers["content-disposition"]


def test_download_supports_range_requests(
    test_client: TestClient, published_sample_data, create_asset
):
    """A download can be limited to part of a file, which allows interrupted downloads
    to be resumed.
    """
    asset = create_asset(published_sample_data["records"][0])
    response = test_client.get(_download_url(asset), headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.content == _FILE_CONTENTS[:10]


def test_download_draft_record_asset_anonymously_is_404(
    test_client: TestClient, sample_survey_related_records, create_asset
):
    """A data file of a draft survey-related record cannot be downloaded by an anonymous
    visitor and is reported as not found.
    """
    asset = create_asset(sample_survey_related_records[0])
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_draft_record_asset_logged_in(
    test_client: TestClient, sample_survey_related_records, create_asset, logged_in
):
    """A logged-in user can download a data file of a draft survey-related record."""
    asset = create_asset(sample_survey_related_records[0])
    response = test_client.get(_download_url(asset))
    assert response.status_code == 200
    assert response.content == _FILE_CONTENTS


def test_download_non_data_asset_is_404(
    test_client: TestClient, published_sample_data, create_asset
):
    """Assets which are not data files, such as thumbnails, cannot be downloaded through
    the data download and are reported as not found.
    """
    asset = create_asset(
        published_sample_data["records"][0],
        asset_type=[constants.AssetType.THUMBNAIL],
    )
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_missing_file_is_404(
    test_client: TestClient, published_sample_data, create_asset
):
    """Downloading an asset whose file is missing from the archive reports it as not
    found.
    """
    asset = create_asset(published_sample_data["records"][0], write_file=False)
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_path_outside_archive_is_404(
    test_client: TestClient, published_sample_data, create_asset, archive_root
):
    """An asset whose path points outside the file archive cannot be downloaded, even if
    a file exists at that location, and is reported as not found.
    """
    # a file that exists, but outside of the archive root
    outside = archive_root.parent / f"{archive_root.name}-outside.txt"
    outside.write_bytes(_FILE_CONTENTS)
    record = published_sample_data["records"][0]
    mission_depth = len(
        next(
            m
            for m in published_sample_data["missions"]
            if m.id == record.survey_mission_id
        ).relative_path.split("/")
    )
    asset = create_asset(
        record,
        relative_path="/".join([".."] * (mission_depth + 1) + [outside.name]),
        write_file=False,
    )
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_shapefile_is_zip_bundle_with_sidecars(
    test_client: TestClient, published_sample_data, create_asset, archive_root
):
    """A shapefile is downloaded as a zip file holding the shapefile together with all
    of its companion files, including large ones, and no files of other datasets in the
    same directory.
    """
    record = published_sample_data["records"][0]
    asset = create_asset(record, relative_path="shapes/FOO.shp")
    mission = next(
        m for m in published_sample_data["missions"] if m.id == record.survey_mission_id
    )
    shapes_dir = archive_root / mission.relative_path / "shapes"
    sidecars = {
        "FOO.shx": b"index",
        # bigger than the streaming chunk size, to have it span several chunks
        "FOO.dbf": os.urandom(3 * 1024**2),
        "foo.prj": b"projection",
        "FOO.shp.xml": b"<metadata/>",
    }
    for name, contents in sidecars.items():
        (shapes_dir / name).write_bytes(contents)
    # files belonging to other datasets
    (shapes_dir / "FOO.other.shp").write_bytes(b"another dataset")
    (shapes_dir / "FOO_v2.dbf").write_bytes(b"another dataset")
    (shapes_dir / "OTHER.shp").write_bytes(b"another dataset")

    response = test_client.get(_download_url(asset))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="FOO.zip"' in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert {info.filename: archive.read(info) for info in archive.infolist()} == {
            "FOO.shp": _FILE_CONTENTS,
            **sidecars,
        }


def _get_download_links(test_client: TestClient, selection: dict) -> dict[str, str]:
    """Fetch the download links of a selection, as a mapping of URL path to output path."""
    response = test_client.get(
        "/survey-related-records/download-links",
        params={"selection": json.dumps(selection)},
    )
    assert response.status_code == 200
    assert 'filename="download-links.txt"' in response.headers["content-disposition"]
    lines = [line for line in response.text.splitlines() if not line.startswith("#")]
    urls, outputs = lines[::2], lines[1::2]
    assert all(output.startswith("  out=") for output in outputs)
    return {
        urllib.parse.urlparse(url).path: output.removeprefix("  out=")
        for url, output in zip(urls, outputs, strict=True)
    }


def _record_path(record: models.SurveyRelatedRecord) -> str:
    return f"/survey-related-records/{record.id}/"


def test_download_links_of_selected_records(
    test_client: TestClient, published_sample_data, create_asset
):
    """The list of download links for selected records contains one link per data file
    of those records, each with its path in the archive as the destination, shapefiles
    as zip files, and nothing for thumbnails or for records not selected.
    """
    selected, unselected = published_sample_data["records"][:2]
    missions = {m.id: m for m in published_sample_data["missions"]}
    mission_path = missions[selected.survey_mission_id].relative_path
    data_asset = create_asset(selected)
    shapefile_asset = create_asset(selected, relative_path="shapes/FOO.shp")
    thumbnail_asset = create_asset(selected, asset_type=[constants.AssetType.THUMBNAIL])
    create_asset(unselected)

    links = _get_download_links(test_client, {"selectedIds": {str(selected.id): True}})
    assert links[_download_url(data_asset)] == f"{mission_path}/some/dir/file.xyz"
    # shapefiles are downloaded as a zip bundle with their sidecars
    assert links[_download_url(shapefile_asset)] == f"{mission_path}/shapes/FOO.zip"
    # only data assets get a download link
    assert _download_url(thumbnail_asset) not in links
    assert all(url.startswith(_record_path(selected)) for url in links)


def test_download_links_of_all_matching_records_skip_the_excluded(
    test_client: TestClient, published_sample_data, create_asset
):
    """When all records matching a search are selected, the list of download links
    leaves out the records that were explicitly deselected.
    """
    excluded, included = published_sample_data["records"][:2]
    create_asset(excluded)
    included_asset = create_asset(included)
    links = _get_download_links(
        test_client,
        {"selectAllMatching": True, "excludedIds": {str(excluded.id): True}},
    )
    assert _download_url(included_asset) in links
    assert not any(url.startswith(_record_path(excluded)) for url in links)


def test_download_links_can_be_scoped_to_a_survey_mission(
    test_client: TestClient, published_sample_data, create_asset
):
    """The list of download links for all matching records can be restricted to a single
    survey mission, and then covers every record of that mission and no others.
    """
    records = published_sample_data["records"]
    for record in records:
        create_asset(record)
    mission_id = records[0].survey_mission_id
    links = _get_download_links(
        test_client,
        {"selectAllMatching": True, "surveyMissionId": str(mission_id)},
    )
    in_mission = [r for r in records if r.survey_mission_id == mission_id]
    assert all(
        any(url.startswith(_record_path(r)) for r in in_mission) for url in links
    )
    assert all(
        any(url.startswith(_record_path(r)) for url in links) for r in in_mission
    )


def test_download_links_only_include_published_records(
    test_client: TestClient, sample_survey_related_records, create_asset, logged_in
):
    """The list of download links contains only published survey-related records, even
    when requested by a logged-in user, since the links are used by download tools which
    are not logged in.
    """
    # the links are fetched by a download tool, without the browser's session
    record = sample_survey_related_records[0]
    create_asset(record)
    assert _get_download_links(test_client, {"selectAllMatching": True}) == {}
    assert (
        _get_download_links(test_client, {"selectedIds": {str(record.id): True}}) == {}
    )


def test_download_links_of_an_empty_selection_are_empty(
    test_client: TestClient, published_sample_data, create_asset
):
    """The list of download links for an empty selection contains no links."""
    create_asset(published_sample_data["records"][0])
    assert _get_download_links(test_client, {}) == {}


def test_download_links_output_paths_stay_inside_the_download_dir(
    test_client: TestClient, published_sample_data, create_asset
):
    """In the list of download links, the destination of each file always lies inside
    the download directory, even when the asset's path in the archive points elsewhere.
    """
    record = published_sample_data["records"][0]
    asset = create_asset(
        record, relative_path="../../../elsewhere/file.xyz", write_file=False
    )
    links = _get_download_links(test_client, {"selectedIds": {str(record.id): True}})
    output_path = links[_download_url(asset)]
    assert ".." not in output_path.split("/")
    assert not output_path.startswith("/")
    assert output_path.endswith("elsewhere/file.xyz")
