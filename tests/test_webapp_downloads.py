import io
import os
import zipfile

import pytest
import sqlmodel
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.schemas import (
    identifiers,
    user as user_schemas,
)
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration

_FILE_CONTENTS = b"0123456789abcdefghij"


@pytest.fixture
def archive_root(settings, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "readonly_archive_root_directory", tmp_path)
    return tmp_path


@pytest.fixture
def logged_in(monkeypatch):
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
    asset = create_asset(published_sample_data["records"][0])
    response = test_client.get(_download_url(asset))
    assert response.status_code == 200
    assert response.content == _FILE_CONTENTS
    assert response.headers["content-type"].startswith("text/plain")
    assert 'filename="file.xyz"' in response.headers["content-disposition"]


def test_download_supports_range_requests(
    test_client: TestClient, published_sample_data, create_asset
):
    asset = create_asset(published_sample_data["records"][0])
    response = test_client.get(_download_url(asset), headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.content == _FILE_CONTENTS[:10]


def test_download_draft_record_asset_anonymously_is_404(
    test_client: TestClient, sample_survey_related_records, create_asset
):
    asset = create_asset(sample_survey_related_records[0])
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_draft_record_asset_logged_in(
    test_client: TestClient, sample_survey_related_records, create_asset, logged_in
):
    asset = create_asset(sample_survey_related_records[0])
    response = test_client.get(_download_url(asset))
    assert response.status_code == 200
    assert response.content == _FILE_CONTENTS


def test_download_non_data_asset_is_404(
    test_client: TestClient, published_sample_data, create_asset
):
    asset = create_asset(
        published_sample_data["records"][0],
        asset_type=[constants.AssetType.THUMBNAIL],
    )
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_missing_file_is_404(
    test_client: TestClient, published_sample_data, create_asset
):
    asset = create_asset(published_sample_data["records"][0], write_file=False)
    response = test_client.get(_download_url(asset))
    assert response.status_code == 404


def test_download_path_outside_archive_is_404(
    test_client: TestClient, published_sample_data, create_asset, archive_root
):
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
