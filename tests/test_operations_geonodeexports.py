"""Tests for exporting survey-related records to GeoNode.

GeoNode is faked: its API is served by an `httpx.MockTransport` and the upload,
which goes out through its own sync client, is replaced altogether.
"""

import datetime as dt
import functools
import json
import uuid

import httpx
import pytest
from sqlalchemy import update

from seis_lab_data import (
    config,
    constants,
    geonode,
)
from seis_lab_data.db import models
from seis_lab_data.db.commands import surveyrelatedrecords as record_commands
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.operations import (
    geonodeexports as export_ops,
    surveyrelatedrecords as record_ops,
)
from seis_lab_data.schemas import (
    events as event_schemas,
    identifiers,
)
from seis_lab_data.schemas.user import User
from seis_lab_data.schemas.identifiers import (
    RequestId,
    UserId,
)

_EXISTING_PK = 7
_NEW_PK = 8


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


class _FakeGeoNode:
    def __init__(self, existing_pks=(), execution_status="finished"):
        self.existing_pks = set(existing_pks)
        self.execution_status = execution_status
        self.uploads = []
        self.metadata_updates = {}

    def upload_dataset(self, api_url, token, files, resource_pk=None):
        self.uploads.append({"files": files, "resource_pk": resource_pk})
        return "exec-1"

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.startswith("/api/v2/resources/"):
            pk = int(path.rstrip("/").rsplit("/", 1)[-1])
            return httpx.Response(200 if pk in self.existing_pks else 404, json={})
        if request.method == "GET" and path == "/api/v2/executionrequest/exec-1":
            resource_pk = self.uploads[-1]["resource_pk"] or _NEW_PK
            return httpx.Response(
                200,
                json={
                    "request": {
                        "status": self.execution_status,
                        "step": "geonode.upload.create_geonode_resource",
                        "log": "the import broke",
                        "output_params": {
                            "resources": [
                                {
                                    "id": resource_pk,
                                    "detail_url": f"/catalogue/#/dataset/{resource_pk}",
                                }
                            ]
                        },
                    }
                },
            )
        if request.method == "PATCH" and path.startswith("/api/v2/resources/"):
            pk = int(path.rsplit("/", 1)[-1])
            self.metadata_updates[pk] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "resource": {
                        "pk": str(pk),
                        "detail_url": f"http://geonode.test/catalogue/#/dataset/{pk}",
                    }
                },
            )
        return httpx.Response(500)


@pytest.fixture
def export_settings(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "target_geonode",
        config.TargetGeoNodeSettings(url="http://geonode.test", token="secret"),
    )
    monkeypatch.setattr(settings, "readonly_archive_root_directory", tmp_path)
    monkeypatch.setattr(settings, "public_url", "http://sld.test")
    return settings


def _install_fake_geonode(monkeypatch, fake: _FakeGeoNode) -> None:
    monkeypatch.setattr(
        export_ops.httpx,
        "AsyncClient",
        functools.partial(
            httpx.AsyncClient, transport=httpx.MockTransport(fake.handle)
        ),
    )
    monkeypatch.setattr(export_ops.geonode, "upload_dataset", fake.upload_dataset)


async def _make_exportable_record(
    session, record: models.SurveyRelatedRecord, archive_root, status
) -> identifiers.SurveyRelatedRecordId:
    record_id = identifiers.SurveyRelatedRecordId(record.id)
    db_record = await record_queries.get_survey_related_record(session, record_id)
    data_dir = archive_root / db_record.survey_mission.relative_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "points.geojson").write_text('{"type": "FeatureCollection"}')
    session.add(
        models.RecordAsset(
            name="points",
            survey_related_record_id=record.id,
            relative_path="data/points.geojson",
            media_type="application/geo+json",
            asset_type=[constants.AssetType.DATA],
        )
    )
    await session.commit()
    await record_commands.set_survey_related_record_status(session, record_id, status)
    return record_id


async def _export(session, record_id, user, settings) -> _EventCollector:
    dispatcher = _EventCollector()
    await export_ops.export_survey_related_record(
        request_id=RequestId(uuid.uuid4()),
        survey_related_record_id=record_id,
        initiator=user,
        session=session,
        event_dispatcher=dispatcher,
        settings=settings,
    )
    return dispatcher


def test_get_upload_files_sends_shapefile_sidecars(tmp_path):
    for name in ("roads.shp", "roads.dbf", "roads.shx", "roads.prj", "roads.cpg"):
        (tmp_path / name).write_bytes(b"")
    # another dataset, whose stem merely starts like the shapefile's
    (tmp_path / "roads2.dbf").write_bytes(b"")

    files = geonode.get_upload_files(tmp_path / "roads.shp")

    assert files == {
        "base_file": tmp_path / "roads.shp",
        "dbf_file": tmp_path / "roads.dbf",
        "shx_file": tmp_path / "roads.shx",
        "prj_file": tmp_path / "roads.prj",
    }


def test_exportable_data_asset_is_the_first_one_geonode_supports():
    def asset(name, relative_path, asset_type=constants.AssetType.DATA):
        return models.RecordAsset(
            name=name,
            relative_path=relative_path,
            media_type="",
            asset_type=[asset_type],
        )

    record = models.SurveyRelatedRecord(
        name="a record",
        assets=[
            asset("c", "c.tif"),
            asset("a", "a.kmall"),
            asset("b", "b.gpkg"),
            asset("0", None, constants.AssetType.PREVIEW),
        ],
    )

    assert export_ops.get_geonode_exportable_data_asset(record).name == "b"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_creates_a_geonode_resource_for_a_record(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    export_settings,
    monkeypatch,
):
    fake = _FakeGeoNode()
    _install_fake_geonode(monkeypatch, fake)
    async with db_session_maker() as session:
        record_id = await _make_exportable_record(
            session,
            sample_survey_related_records[0],
            export_settings.readonly_archive_root_directory,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
        )
        dispatcher = await _export(session, record_id, admin_user, export_settings)
        exported = await record_queries.get_survey_related_record(session, record_id)

    assert [u["resource_pk"] for u in fake.uploads] == [None]
    assert fake.uploads[0]["files"]["base_file"].name == "points.geojson"
    metadata = fake.metadata_updates[_NEW_PK]
    assert metadata["title"] == exported.name
    assert metadata["supplemental_information"].endswith(
        f"http://sld.test/survey-related-records/{record_id}"
    )
    assert exported.geonode_resource_url == (
        f"http://geonode.test/catalogue/#/dataset/{_NEW_PK}"
    )
    assert exported.geonode_exported_at is not None
    assert exported.status == constants.SurveyRelatedRecordStatus.PUBLISHED
    assert dispatcher.events[0].stage == constants.ExportStage.STARTED
    assert dispatcher.events[-1].stage == constants.ExportStage.ENDED
    assert dispatcher.events[-1].succeeded is True


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "existing_pks, expected_resource_pk",
    [
        pytest.param({_EXISTING_PK}, _EXISTING_PK, id="replaces-existing-resource"),
        pytest.param(set(), None, id="recreates-resource-gone-from-geonode"),
    ],
)
async def test_export_of_an_already_exported_record(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    export_settings,
    monkeypatch,
    existing_pks,
    expected_resource_pk,
):
    fake = _FakeGeoNode(existing_pks=existing_pks)
    _install_fake_geonode(monkeypatch, fake)
    async with db_session_maker() as session:
        record_id = await _make_exportable_record(
            session,
            sample_survey_related_records[0],
            export_settings.readonly_archive_root_directory,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
        )
        await record_commands.set_survey_related_record_geonode_export(
            session,
            record_id,
            f"http://geonode.test/catalogue/#/dataset/{_EXISTING_PK}",
            dt.datetime(2026, 1, 23, tzinfo=dt.timezone.utc),
        )
        await _export(session, record_id, admin_user, export_settings)

    assert [u["resource_pk"] for u in fake.uploads] == [expected_resource_pk]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_export_publishes_the_record_again(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    export_settings,
    monkeypatch,
):
    _install_fake_geonode(monkeypatch, _FakeGeoNode(execution_status="failed"))
    async with db_session_maker() as session:
        record_id = await _make_exportable_record(
            session,
            sample_survey_related_records[0],
            export_settings.readonly_archive_root_directory,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
        )
        dispatcher = await _export(session, record_id, admin_user, export_settings)
        record = await record_queries.get_survey_related_record(session, record_id)

    assert record.status == constants.SurveyRelatedRecordStatus.PUBLISHED
    assert record.geonode_resource_url is None
    assert dispatcher.events[-1].succeeded is False
    assert "the import broke" in dispatcher.events[-1].details


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, roles",
    [
        pytest.param(
            constants.SurveyRelatedRecordStatus.DRAFT,
            [constants.ROLE_EDITOR],
            id="draft-record",
        ),
        pytest.param(
            constants.SurveyRelatedRecordStatus.PUBLISHED, [], id="user-without-role"
        ),
    ],
)
async def test_export_is_refused(
    db,
    db_session_maker,
    sample_survey_related_records,
    export_settings,
    monkeypatch,
    status,
    roles,
):
    fake = _FakeGeoNode()
    _install_fake_geonode(monkeypatch, fake)
    user = User(id=UserId("someone"), username="someone", email="a@b.dev", roles=roles)
    async with db_session_maker() as session:
        record_id = await _make_exportable_record(
            session,
            sample_survey_related_records[0],
            export_settings.readonly_archive_root_directory,
            status,
        )
        dispatcher = await _export(session, record_id, user, export_settings)
        record = await record_queries.get_survey_related_record(session, record_id)

    assert fake.uploads == []
    assert record.status == status
    assert [(e.stage, e.succeeded) for e in dispatcher.events] == [
        (constants.ExportStage.ENDED, False)
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_under_export_cannot_be_deleted(
    db, db_session_maker, sample_survey_related_records, admin_user
):
    record_id = identifiers.SurveyRelatedRecordId(sample_survey_related_records[0].id)
    async with db_session_maker() as session:
        await record_commands.set_survey_related_record_status(
            session, record_id, constants.SurveyRelatedRecordStatus.UNDER_EXPORT
        )
        dispatcher = _EventCollector()
        await record_ops.delete_survey_related_record(
            request_id=RequestId(uuid.uuid4()),
            survey_related_record_id=record_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert await record_queries.get_survey_related_record(session, record_id)
    assert dispatcher.events[-1].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_publication_leaves_record_under_export_alone(
    db, db_session_maker, sample_survey_related_records
):
    record = sample_survey_related_records[0]
    record_id = identifiers.SurveyRelatedRecordId(record.id)
    async with db_session_maker() as session:
        await record_commands.update_survey_related_record_validation_result(
            session,
            await record_queries.get_survey_related_record(session, record_id),
            {"is_valid": True, "errors": None},
        )
        await record_commands.set_survey_related_record_status(
            session, record_id, constants.SurveyRelatedRecordStatus.UNDER_EXPORT
        )
        await record_commands.bulk_publish_valid_survey_related_records(
            session, identifiers.SurveyMissionId(record.survey_mission_id)
        )
        found = await record_queries.get_survey_related_record(session, record_id)
    assert found.status == constants.SurveyRelatedRecordStatus.UNDER_EXPORT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_abandoned_exports_are_recovered(
    db, db_session_maker, sample_survey_related_records
):
    stale_id, fresh_id = (
        identifiers.SurveyRelatedRecordId(r.id)
        for r in sample_survey_related_records[:2]
    )
    async with db_session_maker() as session:
        for record_id in (stale_id, fresh_id):
            await record_commands.compare_and_set_survey_related_record_status(
                session,
                record_id,
                constants.SurveyRelatedRecordStatus.DRAFT,
                constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
            )
        await session.execute(
            update(models.SurveyRelatedRecord)
            .where(models.SurveyRelatedRecord.id == stale_id)
            .values(updated_at=dt.datetime(2020, 1, 1))
        )
        await session.commit()
        dispatcher = _EventCollector()
        await export_ops.recover_stale_geonode_exports(
            request_id=RequestId(uuid.uuid4()),
            session=session,
            event_dispatcher=dispatcher,
        )
        stale = await record_queries.get_survey_related_record(session, stale_id)
        fresh = await record_queries.get_survey_related_record(session, fresh_id)

    assert stale.status == constants.SurveyRelatedRecordStatus.PUBLISHED
    # its status change stamped updated_at, which is what tells it is not stale
    assert fresh.updated_at is not None
    assert fresh.status == constants.SurveyRelatedRecordStatus.UNDER_EXPORT
    assert [e.resource_id for e in dispatcher.events] == [str(stale_id)]
