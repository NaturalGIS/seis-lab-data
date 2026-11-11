"""Tests for exporting survey-related records to GeoNode.

GeoNode is faked: its API, uploads included, is served by an `httpx.MockTransport`.
"""

import base64
import datetime as dt
import functools
import email.parser
import email.policy
import json
import uuid

import anyio
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
_ACCESS_TOKEN = "issued-token"


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


class _FakeGeoNode:
    def __init__(
        self, existing_pks=(), execution_status="finished", issues_tokens=True
    ):
        self.existing_pks = set(existing_pks)
        self.execution_status = execution_status
        self.issues_tokens = issues_tokens
        self.token_requests = []
        self.revoked_tokens = []
        self.uploads = []
        self.metadata_updates = {}

    def _receive_upload(self, request: httpx.Request) -> httpx.Response:
        form = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode()
            + request.content
        )
        parts = {
            part.get_param("name", header="Content-Disposition"): part
            for part in form.iter_parts()
        }
        resource_pk = parts.get("resource_pk")
        self.uploads.append(
            {
                "action": parts["action"].get_content(),
                "resource_pk": (
                    int(resource_pk.get_content()) if resource_pk is not None else None
                ),
                "files": {
                    name: part.get_filename()
                    for name, part in parts.items()
                    if part.get_filename() is not None
                },
            }
        )
        return httpx.Response(201, json={"execution_id": "exec-1"})

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/o/token/":
            self.token_requests.append(
                {
                    "authorization": request.headers.get("Authorization"),
                    "form": dict(httpx.QueryParams(request.content.decode())),
                }
            )
            if not self.issues_tokens:
                return httpx.Response(401, json={"error": "invalid_client"})
            return httpx.Response(
                200, json={"access_token": _ACCESS_TOKEN, "token_type": "Bearer"}
            )
        if request.method == "POST" and path == "/o/revoke_token/":
            self.revoked_tokens.append(
                dict(httpx.QueryParams(request.content.decode()))["token"]
            )
            return httpx.Response(200)
        if request.headers.get("Authorization") != f"Bearer {_ACCESS_TOKEN}":
            return httpx.Response(401, json={"detail": "not authenticated"})
        if request.method == "POST" and path == "/api/v2/uploads/upload":
            return self._receive_upload(request)
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
        config.TargetGeoNodeSettings(
            url="http://geonode.test",
            username="exporter",
            password="exporter-pass",
            client_id="client-id",
            client_secret="client-secret",
        ),
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


async def _make_exportable_record(
    session,
    record: models.SurveyRelatedRecord,
    archive_root,
    status,
    data_file_names=("points.geojson",),
) -> identifiers.SurveyRelatedRecordId:
    """Give the record a data asset, backed by the first of the data files."""
    record_id = identifiers.SurveyRelatedRecordId(record.id)
    db_record = await record_queries.get_survey_related_record(session, record_id)
    data_dir = archive_root / db_record.survey_mission.relative_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in data_file_names:
        (data_dir / name).write_bytes(b"")
    session.add(
        models.RecordAsset(
            name="points",
            survey_related_record_id=record.id,
            relative_path=f"data/{data_file_names[0]}",
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


@pytest.mark.asyncio
async def test_get_upload_files_sends_shapefile_sidecars(tmp_path):
    for name in ("roads.shp", "roads.dbf", "roads.shx", "roads.prj", "roads.cpg"):
        (tmp_path / name).write_bytes(b"")
    # another dataset, whose stem merely starts like the shapefile's
    (tmp_path / "roads2.dbf").write_bytes(b"")

    files = await geonode.get_upload_files(anyio.Path(tmp_path, "roads.shp"))

    assert {field: path.name for field, path in files.items()} == {
        "base_file": "roads.shp",
        "dbf_file": "roads.dbf",
        "shx_file": "roads.shx",
        "prj_file": "roads.prj",
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
    assert fake.uploads[0]["action"] == "upload"
    assert fake.uploads[0]["files"] == {"base_file": "points.geojson"}
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
    # the record's status changes are announced, for pages showing it to follow
    status_changes = [
        e.new_status
        for e in dispatcher.events
        if isinstance(e, event_schemas.ResourceStatusChangedEvent)
    ]
    assert status_changes == [
        constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
        constants.SurveyRelatedRecordStatus.PUBLISHED,
    ]
    export_stages = [
        e.stage for e in dispatcher.events if isinstance(e, event_schemas.ExportEvent)
    ]
    assert export_stages[0] == constants.ExportStage.STARTED
    assert export_stages[-1] == constants.ExportStage.ENDED
    assert dispatcher.events[-1].succeeded is True
    # the service account's credentials are exchanged for an access token, the
    # OAuth app authenticating with basic auth, and the token revoked when done
    assert fake.token_requests == [
        {
            "authorization": (
                f"Basic {base64.b64encode(b'client-id:client-secret').decode()}"
            ),
            "form": {
                "grant_type": "password",
                "username": "exporter",
                "password": "exporter-pass",
            },
        }
    ]
    assert fake.revoked_tokens == [_ACCESS_TOKEN]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_of_a_shapefile_sends_its_sidecars(
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
            data_file_names=("points.shp", "points.dbf", "points.shx", "points.prj"),
        )
        dispatcher = await _export(session, record_id, admin_user, export_settings)

    assert dispatcher.events[-1].succeeded is True
    assert fake.uploads[0]["files"] == {
        "base_file": "points.shp",
        "dbf_file": "points.dbf",
        "shx_file": "points.shx",
        "prj_file": "points.prj",
    }


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
async def test_export_failing_unexpectedly_is_reported(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    export_settings,
    monkeypatch,
):
    async def broken_get_upload_files(data_path):
        raise TypeError("something unforeseen")

    _install_fake_geonode(monkeypatch, _FakeGeoNode())
    monkeypatch.setattr(export_ops.geonode, "get_upload_files", broken_get_upload_files)
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
    assert dispatcher.events[-1].stage == constants.ExportStage.ENDED
    assert dispatcher.events[-1].succeeded is False
    assert "something unforeseen" in dispatcher.events[-1].details


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_fails_when_geonode_refuses_the_credentials(
    db,
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    export_settings,
    monkeypatch,
):
    fake = _FakeGeoNode(issues_tokens=False)
    _install_fake_geonode(monkeypatch, fake)
    async with db_session_maker() as session:
        record_id = await _make_exportable_record(
            session,
            sample_survey_related_records[0],
            export_settings.readonly_archive_root_directory,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
        )
        dispatcher = await _export(session, record_id, admin_user, export_settings)
        record = await record_queries.get_survey_related_record(session, record_id)

    assert fake.uploads == []
    assert record.status == constants.SurveyRelatedRecordStatus.PUBLISHED
    assert dispatcher.events[-1].succeeded is False
    assert "invalid_client" in dispatcher.events[-1].details


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
    assert [(type(e), e.resource_id) for e in dispatcher.events] == [
        (event_schemas.ResourceStatusChangedEvent, str(stale_id)),
        (event_schemas.ExportEvent, str(stale_id)),
    ]
