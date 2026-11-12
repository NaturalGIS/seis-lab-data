"""Integration tests for mission discovery with metadata extraction, for the
derivation of previews which it kicks off and for the same pipeline run over
records created or edited by hand.

These run against the test database and a fake archive built under tmp_path.
GDAL is required to build the synthetic fixture files; the module self-skips
where it is unavailable.
"""

import asyncio
import dataclasses
import datetime as dt
import inspect
import json
import logging
import math
import uuid

import pytest
import pytest_asyncio
import shapely
import sqlalchemy
import sqlmodel
from geoalchemy2.shape import to_shape

pytest.importorskip("osgeo")

from osgeo import gdal, osr  # noqa: E402

from seis_lab_data import constants  # noqa: E402
from seis_lab_data.db import models  # noqa: E402
from seis_lab_data.db.commands import (  # noqa: E402
    discovery as discovery_commands,
    projects as project_commands,
    surveymissions as mission_commands,
)
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries  # noqa: E402
from seis_lab_data.operations import (  # noqa: E402
    discovery as discovery_ops,
    previews as preview_ops,
    surveyrelatedrecords as record_ops,
)
from seis_lab_data.schemas import (  # noqa: E402
    discovery as discovery_schemas,
    events as event_schemas,
    identifiers,
    projects as project_schemas,
    surveymissions as mission_schemas,
    surveyrelatedrecords as record_schemas,
)
from seis_lab_data.tasks import previews as preview_tasks  # noqa: E402
from seis_lab_data.tasks.derivers import schemas as deriver_schemas  # noqa: E402
from seis_lab_data.tasks.extractors import schemas as extractor_schemas  # noqa: E402

gdal.UseExceptions()

_MISSION_RELATIVE_PATH = "surveys/test-mission"
# ETRS89/PT-TM06 metres, around the projection origin in central Portugal
_NATIVE_BBOX_TM06 = (0.0, 1900.0, 100.0, 2000.0)
# a bbox drawn by the user, well away from the one of the synthetic grids
_DRAWN_BBOX_WKT = "POLYGON((-9 38, -8.9 38, -8.9 38.1, -9 38.1, -9 38))"


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


def _write_geotiff(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3763)
    ds = gdal.GetDriverByName("GTiff").Create(str(path), 10, 10, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((0.0, 10.0, 0.0, 2000.0, 0.0, -10.0))
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).SetNoDataValue(-9999.0)
    ds.GetRasterBand(1).Fill(1.0)
    ds = None


async def _create_mission(session, project_id, mission_relative_path, name_suffix=""):
    mission = await mission_commands.create_survey_mission(
        session,
        mission_schemas.SurveyMissionCreate(
            id=identifiers.SurveyMissionId(uuid.uuid4()),
            project_id=project_id,
            name=f"Discovery test mission{name_suffix}",
            description="",
            relative_path=mission_relative_path,
        ),
    )
    return mission


@pytest_asyncio.fixture
async def discovery_env(
    tmp_path,
    settings,
    db,
    db_session_maker,
    bootstrap_dataset_categories,
    bootstrap_workflow_stages,
):
    """A fake archive plus one project, mission and discovery configuration."""
    settings.readonly_archive_root_directory = tmp_path
    async with db_session_maker() as session:
        project = await project_commands.create_project(
            session,
            project_schemas.ProjectCreate(
                id=identifiers.ProjectId(uuid.uuid4()),
                name="Discovery test project",
            ),
        )
        mission = await _create_mission(
            session,
            identifiers.ProjectId(project.id),
            _MISSION_RELATIVE_PATH,
        )
        configuration = await discovery_commands.create_asset_discovery_configuration(
            session,
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
                name="test tif",
                relative_path_regexp=r"s01/.*\.tif",
                media_type="image/tiff",
                generate_previews=True,
                workflow_stage_id=identifiers.WorkflowStageId(
                    bootstrap_workflow_stages[0].id
                ),
                dataset_category_id=identifiers.DatasetCategoryId(
                    bootstrap_dataset_categories[0].id
                ),
            ),
        )
    return {
        "archive_root": tmp_path,
        "settings": settings,
        "project": project,
        "mission": mission,
        "configuration": configuration,
    }


async def _run_discovery(db_session_maker, mission_id, settings, admin_user):
    collector = _EventCollector()
    async with db_session_maker() as session:
        await discovery_ops.run_mission_discovery(
            request_id=identifiers.RequestId(uuid.uuid4()),
            mission_id=identifiers.SurveyMissionId(mission_id),
            session=session,
            event_dispatcher=collector,
            settings=settings,
            user=admin_user,
        )
    return collector


async def _get_mission_records(db_session_maker, mission_id):
    async with db_session_maker() as session:
        statement = sqlmodel.select(models.SurveyRelatedRecord).where(
            models.SurveyRelatedRecord.survey_mission_id == mission_id
        )
        return (await session.exec(statement)).all()


async def _get_record_assets(db_session_maker, record_id):
    async with db_session_maker() as session:
        statement = sqlmodel.select(models.RecordAsset).where(
            models.RecordAsset.survey_related_record_id == record_id
        )
        return (await session.exec(statement)).all()


def _ended_events(collector):
    return [
        e
        for e in collector.events
        if isinstance(e, event_schemas.DiscoveryEvent)
        and e.modification == constants.DiscoveryStage.ENDED
    ]


def _record_to_create(discovery_env, relative_path):
    configuration = discovery_env["configuration"]
    return record_schemas.SurveyRelatedRecordCreate(
        id=identifiers.SurveyRelatedRecordId(uuid.uuid4()),
        survey_mission_id=identifiers.SurveyMissionId(discovery_env["mission"].id),
        name="Manual record",
        description="A record created by hand",
        dataset_category_id=identifiers.DatasetCategoryId(
            configuration.dataset_category_id
        ),
        workflow_stage_id=identifiers.WorkflowStageId(configuration.workflow_stage_id),
        assets=[
            record_schemas.DataRecordAssetCreate(
                id=identifiers.RecordAssetId(uuid.uuid4()),
                name="data file",
                relative_path=relative_path,
            )
        ],
    )


async def _create_record_without_discovery(db_session_maker, admin_user, to_create):
    async with db_session_maker() as session:
        await record_ops.create_survey_related_record(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_create=to_create,
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
        )


async def _update_record_by_hand(
    db_session_maker, admin_user, settings, record_id, to_update
):
    async with db_session_maker() as session:
        await discovery_ops.update_manual_survey_related_record(
            request_id=identifiers.RequestId(uuid.uuid4()),
            survey_related_record_id=identifiers.SurveyRelatedRecordId(record_id),
            to_update=to_update,
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
            settings=settings,
        )


def test_bbox_tuple_to_wkt_buffers_every_side():
    wkt = discovery_ops._bbox_4326_tuple_to_wkt((10.0, 40.0, 10.5, 40.5))
    assert shapely.from_wkt(wkt).bounds == pytest.approx(
        (9.9999, 39.9999, 10.5001, 40.5001)
    )


def test_bbox_tuple_to_wkt_pads_degenerate_point():
    wkt = discovery_ops._bbox_4326_tuple_to_wkt((-8.5, 39.0, -8.5, 39.0))
    polygon = shapely.from_wkt(wkt)
    assert polygon.is_valid
    assert polygon.area > 0
    assert polygon.bounds == pytest.approx((-8.5001, 38.9999, -8.4999, 39.0001))


def test_bbox_tuple_to_wkt_discards_out_of_range(caplog):
    with caplog.at_level(logging.WARNING, logger=discovery_ops.logger.name):
        result = discovery_ops._bbox_4326_tuple_to_wkt((200.0, 40.0, 201.0, 41.0))
    assert result is None
    assert any("Discarding extracted bbox" in r.message for r in caplog.records)


def test_bbox_tuple_to_wkt_discards_non_finite():
    assert discovery_ops._bbox_4326_tuple_to_wkt((math.nan, 40.0, 10.0, 41.0)) is None
    assert discovery_ops._bbox_4326_tuple_to_wkt((10.0, 40.0, math.inf, 41.0)) is None


def test_bbox_tuple_to_wkt_discards_inverted_bbox():
    assert discovery_ops._bbox_4326_tuple_to_wkt((10.5, 40.0, 10.0, 41.0)) is None


def test_bbox_tuple_to_wkt_rounds_to_five_decimal_places():
    # the frontend's TerraDraw silently drops features with coordinates over 9
    # decimal places, so stored bboxes must come out rounded
    wkt = discovery_ops._bbox_4326_tuple_to_wkt(
        (-9.370596897483855, 40.51113433598111, -9.159202392776214, 40.805561916939304)
    )
    for coordinate in shapely.from_wkt(wkt).exterior.coords:
        for value in coordinate:
            assert value == round(value, 5)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_extracts_metadata(db_session_maker, admin_user, discovery_env):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/sub/grid.tif"
    )

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is True

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    record = records[0]
    assert record.name == "grid.tif"
    assert record.description.startswith("Auto-extracted: GTiff raster")
    assert record.bbox_4326 is not None
    # the synthetic EPSG:3763 grid reprojects to central Portugal
    minx, miny, maxx, maxy = to_shape(record.bbox_4326).bounds
    assert -8.2 < minx <= maxx < -8.0
    assert 39.6 < miny <= maxy < 39.8
    async with db_session_maker() as session:
        statement = sqlmodel.select(models.RecordAsset).where(
            models.RecordAsset.survey_related_record_id == record.id
        )
        assets = (await session.exec(statement)).all()
    assert len(assets) == 1
    assert assets[0].relative_path == "s01/sub/grid.tif"
    # the extracted summary goes on the record only; the asset stays empty
    assert assets[0].description == ""
    # discovered assets are the record's data files, with a media type derived
    # from the file extension
    assert assets[0].asset_type == [constants.AssetType.DATA]
    assert assets[0].media_type == "application/prs.ipma.tif"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_is_idempotent(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    extraction_calls = []
    real_dispatch = discovery_ops.extractor_dispatch.dispatch_extractor

    def counting_dispatch(path):
        extraction_calls.append(path)
        return real_dispatch(path)

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", counting_dispatch
    )

    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    first_records = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    second_collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    assert records[0].id == first_records[0].id
    # dedup runs before extraction and the heal is off under 4326: nothing is extracted
    assert len(extraction_calls) == 1
    # and the second run must not even attempt a record creation (a failed
    # attempt would surface as a succeeded=False modification event)
    assert not any(
        isinstance(e, event_schemas.ResourceModificationEvent) and e.succeeded is False
        for e in second_collector.events
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_dedup_is_scoped_per_mission(
    db_session_maker, admin_user, discovery_env
):
    # the same mission-relative file path exists in two missions: each mission
    # must get its own record (dedup must not be global)
    second_mission_relative_path = "surveys/test-mission-2"
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    _write_geotiff(
        discovery_env["archive_root"] / second_mission_relative_path / "s01/grid.tif"
    )
    async with db_session_maker() as session:
        second_mission = await _create_mission(
            session,
            identifiers.ProjectId(discovery_env["project"].id),
            second_mission_relative_path,
            name_suffix=" 2",
        )

    for mission_id in (discovery_env["mission"].id, second_mission.id):
        await _run_discovery(
            db_session_maker, mission_id, discovery_env["settings"], admin_user
        )

    first_records = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    second_records = await _get_mission_records(db_session_maker, second_mission.id)
    assert len(first_records) == 1
    assert len(second_records) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_survives_extraction_failure(
    db_session_maker, admin_user, discovery_env, caplog
):
    bad_file = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/bad.tif"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_bytes(b"this is not a tif")

    with caplog.at_level(logging.WARNING, logger=discovery_ops.logger.name):
        collector = await _run_discovery(
            db_session_maker,
            discovery_env["mission"].id,
            discovery_env["settings"],
            admin_user,
        )

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is True
    assert any(
        "Metadata extraction failed" in record.message for record in caplog.records
    )

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    record = records[0]
    assert record.name == "bad.tif"
    assert record.description == ""
    assert record.bbox_4326 is None


async def _get_mission_status(db_session_maker, mission_id):
    async with db_session_maker() as session:
        return (await session.get(models.SurveyMission, mission_id)).status


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_survives_a_file_that_fails(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    mission_root = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH
    _write_geotiff(mission_root / "s01/grid.tif")
    _write_geotiff(mission_root / "s01/bad.tif")
    real_create = discovery_ops.record_ops.create_survey_related_record

    async def create_failing_for_bad_file(**kwargs):
        if kwargs["to_create"].name == "bad.tif":
            raise RuntimeError("could not create the record")
        return await real_create(**kwargs)

    monkeypatch.setattr(
        discovery_ops.record_ops,
        "create_survey_related_record",
        create_failing_for_bad_file,
    )

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is True
    assert ended[0].details == (
        "2 files found, 1 new records, 1 files could not be discovered"
    )
    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert [record.name for record in records] == ["grid.tif"]
    assert (
        await _get_mission_status(db_session_maker, discovery_env["mission"].id)
        == constants.SurveyMissionStatus.DRAFT
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_truncates_long_file_names(
    db_session_maker, admin_user, discovery_env
):
    # archive file names can be longer than record and asset names may be
    file_name = f"{'a' * constants.NAME_MAX_LENGTH}.tif"
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01" / file_name
    )

    for _ in range(2):
        collector = await _run_discovery(
            db_session_maker,
            discovery_env["mission"].id,
            discovery_env["settings"],
            admin_user,
        )
        assert _ended_events(collector)[0].succeeded is True

    # the second run finds the file tracked by its full path
    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    assert records[0].name == file_name[: constants.NAME_MAX_LENGTH]
    assets = await _get_record_assets(db_session_maker, records[0].id)
    assert assets[0].name == "a" * constants.NAME_MAX_LENGTH
    assert assets[0].relative_path == f"s01/{file_name}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_skips_configuration_directories_the_mission_lacks(
    db_session_maker,
    admin_user,
    discovery_env,
    bootstrap_dataset_categories,
    bootstrap_workflow_stages,
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    async with db_session_maker() as session:
        await discovery_commands.create_asset_discovery_configuration(
            session,
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
                # sorts before the test configuration, so it is searched first
                name="a directory this mission lacks",
                relative_path_regexp=r"s99/.*\.tif",
                media_type="image/tiff",
                generate_previews=False,
                workflow_stage_id=identifiers.WorkflowStageId(
                    bootstrap_workflow_stages[0].id
                ),
                dataset_category_id=identifiers.DatasetCategoryId(
                    bootstrap_dataset_categories[0].id
                ),
            ),
        )

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is True
    assert ended[0].details == "1 files found, 1 new records"
    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_survives_a_configuration_that_fails(
    db_session_maker,
    admin_user,
    discovery_env,
    bootstrap_dataset_categories,
    bootstrap_workflow_stages,
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    async with db_session_maker() as session:
        await discovery_commands.create_asset_discovery_configuration(
            session,
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
                name="a broken regexp",
                relative_path_regexp=r"s01/(.*\.tif",
                media_type="image/tiff",
                generate_previews=False,
                workflow_stage_id=identifiers.WorkflowStageId(
                    bootstrap_workflow_stages[0].id
                ),
                dataset_category_id=identifiers.DatasetCategoryId(
                    bootstrap_dataset_categories[0].id
                ),
            ),
        )

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is True
    assert ended[0].details == (
        "1 files found, 1 new records, "
        "invalid asset discovery configurations: a broken regexp"
    )
    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_keeps_a_published_mission_published(
    db_session_maker, admin_user, discovery_env
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    mission_id = identifiers.SurveyMissionId(discovery_env["mission"].id)
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, mission_id, constants.SurveyMissionStatus.PUBLISHED
        )

    collector = await _run_discovery(
        db_session_maker, mission_id, discovery_env["settings"], admin_user
    )

    assert _ended_events(collector)[0].succeeded is True
    assert (
        await _get_mission_status(db_session_maker, mission_id)
        == constants.SurveyMissionStatus.PUBLISHED
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, expected_details",
    [
        (RuntimeError("connection details"), "unexpected error (RuntimeError)"),
        (asyncio.CancelledError(), "discovery was interrupted"),
    ],
)
async def test_discovery_that_stops_reports_its_end_and_restores_the_status(
    db_session_maker, admin_user, discovery_env, monkeypatch, error, expected_details
):
    async def failing_discovery(**kwargs):
        raise error

    monkeypatch.setattr(discovery_ops, "_discover_mission_records", failing_discovery)
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_mission_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )
    mission_id = identifiers.SurveyMissionId(discovery_env["mission"].id)
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, mission_id, constants.SurveyMissionStatus.PUBLISHED
        )

    collector = _EventCollector()
    async with db_session_maker() as session:
        try:
            await discovery_ops.run_mission_discovery(
                request_id=identifiers.RequestId(uuid.uuid4()),
                mission_id=mission_id,
                session=session,
                event_dispatcher=collector,
                settings=discovery_env["settings"],
                user=admin_user,
            )
        # an interruption must go on up to dramatiq
        except asyncio.CancelledError:
            assert isinstance(error, asyncio.CancelledError)

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is False
    assert ended[0].details.startswith(expected_details)
    assert enqueued == []
    assert (
        await _get_mission_status(db_session_maker, mission_id)
        == constants.SurveyMissionStatus.PUBLISHED
    )


async def _set_mission_status(db_session_maker, mission_id, status, age=None):
    """Set a mission's status directly, along with how long ago it was updated."""
    async with db_session_maker() as session:
        await session.execute(
            sqlalchemy.update(models.SurveyMission)
            .where(models.SurveyMission.id == mission_id)
            .values(
                status=status,
                updated_at=(
                    sqlalchemy.func.now()
                    if age is None
                    else sqlalchemy.func.now() - age
                ),
            )
        )
        await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_can_be_cancelled_and_keeps_its_records(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    mission_root = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH
    for name in ("a.tif", "b.tif", "c.tif"):
        _write_geotiff(mission_root / "s01" / name)
    mission_id = identifiers.SurveyMissionId(discovery_env["mission"].id)
    monkeypatch.setattr(constants, "DISCOVERY_HEARTBEAT_INTERVAL_SECONDS", 0.01)
    real_extract = discovery_ops._extract_file_metadata

    async def extract_and_request_cancellation(file_path, implicit_crs):
        async with db_session_maker() as session:
            await mission_commands.compare_and_set_survey_mission_status(
                session,
                mission_id,
                constants.SurveyMissionStatus.UNDER_DISCOVERY,
                constants.SurveyMissionStatus.CANCELLING_DISCOVERY,
            )
        # gives the heartbeat time to see the cancellation
        await asyncio.sleep(0.2)
        return await real_extract(file_path, implicit_crs)

    monkeypatch.setattr(
        discovery_ops, "_extract_file_metadata", extract_and_request_cancellation
    )
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_mission_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )

    collector = await _run_discovery(
        db_session_maker, mission_id, discovery_env["settings"], admin_user
    )

    records = await _get_mission_records(db_session_maker, mission_id)
    assert [record.name for record in records] == ["a.tif"]
    assert _ended_events(collector) == []
    cancelled = [
        e
        for e in collector.events
        if isinstance(e, event_schemas.DiscoveryEvent)
        and e.modification == constants.DiscoveryStage.CANCELLED
    ]
    assert [(e.succeeded, e.details) for e in cancelled] == [
        (True, "1 files found, 1 new records")
    ]
    # the records kept get their previews
    assert len(enqueued) == 1
    assert (
        await _get_mission_status(db_session_maker, mission_id)
        == constants.SurveyMissionStatus.DRAFT
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, age, expected_status, expected_event",
    [
        pytest.param(
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
            None,
            constants.SurveyMissionStatus.CANCELLING_DISCOVERY,
            "status changed",
            id="running",
        ),
        pytest.param(
            constants.SurveyMissionStatus.DRAFT,
            None,
            constants.SurveyMissionStatus.DRAFT,
            "not cancelled",
            id="not running",
        ),
        pytest.param(
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
            dt.timedelta(hours=1),
            constants.SurveyMissionStatus.DRAFT,
            "abandoned",
            id="abandoned",
        ),
    ],
)
async def test_cancel_mission_discovery(
    db_session_maker,
    admin_user,
    discovery_env,
    status,
    age,
    expected_status,
    expected_event,
):
    mission_id = identifiers.SurveyMissionId(discovery_env["mission"].id)
    await _set_mission_status(db_session_maker, mission_id, status, age)

    collector = _EventCollector()
    async with db_session_maker() as session:
        await discovery_ops.cancel_mission_discovery(
            request_id=identifiers.RequestId(uuid.uuid4()),
            mission_id=mission_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=collector,
        )

    assert await _get_mission_status(db_session_maker, mission_id) == expected_status
    match expected_event:
        case "status changed":
            assert [
                e.new_status
                for e in collector.events
                if isinstance(e, event_schemas.ResourceStatusChangedEvent)
            ] == [constants.SurveyMissionStatus.CANCELLING_DISCOVERY]
        case "not cancelled":
            assert [
                (e.modification, e.succeeded)
                for e in collector.events
                if isinstance(e, event_schemas.DiscoveryEvent)
            ] == [(constants.DiscoveryStage.CANCELLED, False)]
        case "abandoned":
            ended = _ended_events(collector)
            assert [e.succeeded for e in ended] == [False]
            assert "abandoned" in ended[0].details


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recover_stale_mission_discoveries(
    db_session_maker, admin_user, discovery_env
):
    abandoned_id = identifiers.SurveyMissionId(discovery_env["mission"].id)
    async with db_session_maker() as session:
        running = await _create_mission(
            session,
            identifiers.ProjectId(discovery_env["project"].id),
            "surveys/running",
            name_suffix=" running",
        )
    running_id = identifiers.SurveyMissionId(running.id)
    await _set_mission_status(
        db_session_maker,
        abandoned_id,
        constants.SurveyMissionStatus.CANCELLING_DISCOVERY,
        dt.timedelta(seconds=constants.DISCOVERY_STALE_AFTER_SECONDS + 60),
    )
    await _set_mission_status(
        db_session_maker, running_id, constants.SurveyMissionStatus.UNDER_DISCOVERY
    )

    async with db_session_maker() as session:
        recovered = await discovery_ops.recover_stale_mission_discoveries(
            request_id=identifiers.RequestId(uuid.uuid4()),
            initiator_id="system",
            session=session,
            event_dispatcher=_EventCollector(),
        )

    assert recovered == [abandoned_id]
    assert (
        await _get_mission_status(db_session_maker, abandoned_id)
        == constants.SurveyMissionStatus.DRAFT
    )
    assert (
        await _get_mission_status(db_session_maker, running_id)
        == constants.SurveyMissionStatus.UNDER_DISCOVERY
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_reports_progress_instead_of_record_events(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    mission_root = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH
    for name in ("a.tif", "b.tif"):
        _write_geotiff(mission_root / "s01" / name)
    monkeypatch.setattr(constants, "DISCOVERY_PROGRESS_INTERVAL_SECONDS", 0)

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    assert [
        e.details
        for e in collector.events
        if isinstance(e, event_schemas.DiscoveryEvent)
        and e.modification == constants.DiscoveryStage.PROGRESS
    ] == ["1 files found, 1 new records", "2 files found, 2 new records"]
    assert not any(
        getattr(e, "resource_type", None) == constants.ResourceType.RECORD
        for e in collector.events
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mission_previews_are_collected_for_eligible_records_only(
    db_session_maker, admin_user, discovery_env
):
    eligible = _record_to_create(discovery_env, "s01/grid.tif")
    ineligible = _record_to_create(discovery_env, "other/grid.tif")
    for to_create in (eligible, ineligible):
        await _create_record_without_discovery(db_session_maker, admin_user, to_create)

    async with db_session_maker() as session:
        collected = await preview_ops.collect_survey_mission_records_missing_previews(
            session, identifiers.SurveyMissionId(discovery_env["mission"].id)
        )

    assert collected == [eligible.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_passes_temporal_extent_through(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    # KMALL and SEG-Y do emit temporal dates, but a faked dispatcher keeps this
    # test about the passthrough itself rather than about any one extractor
    target = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/dated.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content is irrelevant, dispatch is faked")

    def fake_dispatch(path):
        return extractor_schemas.RasterMetadata(
            driver="GTiff",
            width=1,
            height=1,
            band_count=1,
            bbox_4326=(-8.2, 39.6, -8.1, 39.7),
            temporal_extent_begin=dt.date(2024, 9, 28),
            temporal_extent_end=dt.date(2024, 9, 29),
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )

    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    record = records[0]
    assert record.temporal_extent_begin == dt.date(2024, 9, 28)
    assert record.temporal_extent_end == dt.date(2024, 9, 29)
    # the stored bbox is the metadata bbox expanded by the always-applied buffer
    assert to_shape(record.bbox_4326).bounds == pytest.approx(
        (-8.2001, 39.5999, -8.0999, 39.7001)
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_applies_mission_implicit_crs(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    # formats that cannot carry a CRS (XYZ grids, SEG-Y) only yield a native
    # bbox: the mission's implicit CRS is what turns it into a map bbox
    target = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/implicit.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content is irrelevant, dispatch is faked")

    def fake_dispatch(path):
        return extractor_schemas.RasterMetadata(
            driver="XYZ",
            width=10,
            height=10,
            band_count=1,
            bbox_native=_NATIVE_BBOX_TM06,
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )
    async with db_session_maker() as session:
        mission = await session.get(models.SurveyMission, discovery_env["mission"].id)
        mission.implicit_crs = 3763
        session.add(mission)
        await session.commit()

    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    # the native bbox reprojects from ETRS89/PT-TM06 to central Portugal
    minx, miny, maxx, maxy = to_shape(records[0].bbox_4326).bounds
    assert -8.2 < minx <= maxx < -8.0
    assert 39.6 < miny <= maxy < 39.8


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_implicit_crs_default_discards_projected_coordinates(
    db_session_maker, admin_user, discovery_env, monkeypatch, caplog
):
    # the 4326 default is a placeholder: metre coordinates then fail the lon/lat
    # range check and the bbox correctly stays NULL
    assert discovery_env["mission"].implicit_crs == 4326
    target = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/metres.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content is irrelevant, dispatch is faked")

    def fake_dispatch(path):
        return extractor_schemas.RasterMetadata(
            driver="XYZ",
            width=10,
            height=10,
            band_count=1,
            bbox_native=_NATIVE_BBOX_TM06,
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )

    with caplog.at_level(logging.WARNING, logger=discovery_ops.logger.name):
        await _run_discovery(
            db_session_maker,
            discovery_env["mission"].id,
            discovery_env["settings"],
            admin_user,
        )

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    assert records[0].bbox_4326 is None
    assert any("Discarding extracted bbox" in r.message for r in caplog.records)
    assert "CRS: unknown." in records[0].description


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_survives_invalid_implicit_crs(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    target = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/bogus.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content is irrelevant, dispatch is faked")

    def fake_dispatch(path):
        return extractor_schemas.RasterMetadata(
            driver="XYZ",
            width=10,
            height=10,
            band_count=1,
            bbox_native=_NATIVE_BBOX_TM06,
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )
    async with db_session_maker() as session:
        mission = await session.get(models.SurveyMission, discovery_env["mission"].id)
        mission.implicit_crs = 999999
        session.add(mission)
        await session.commit()

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    ended = _ended_events(collector)
    assert len(ended) == 1
    assert ended[0].succeeded is True
    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    assert records[0].bbox_4326 is None


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "implicit_crs, header_epsg_codes, expected_crs",
    [
        pytest.param(
            4326,
            (9807, 3763),
            "CRS: ETRS89 / Portugal TM06 (EPSG:3763).",
            id="one projected code",
        ),
        pytest.param(
            3763,
            (3763, 3763),
            "CRS: ETRS89 / Portugal TM06 (EPSG:3763).",
            id="code of the mission, quoted twice",
        ),
        pytest.param(
            3763,
            (3763, 32629),
            "CRS: ETRS89 / Portugal TM06 (EPSG:3763, from the survey mission).",
            id="two projected codes",
        ),
        # with the mission at 4326 too, taking the header's 4326 would go unnoticed
        pytest.param(
            3763,
            (4326,),
            "CRS: ETRS89 / Portugal TM06 (EPSG:3763, from the survey mission).",
            id="geographic code",
        ),
    ],
)
async def test_discovery_applies_header_crs(
    db_session_maker,
    admin_user,
    discovery_env,
    monkeypatch,
    implicit_crs,
    header_epsg_codes,
    expected_crs,
):
    # only a single projected CRS quoted by the SEG-Y header overrides the mission's
    target = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/line.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content is irrelevant, dispatch is faked")

    def fake_dispatch(path):
        return extractor_schemas.SegyMetadata(
            driver="SEG-Y",
            bbox_native=_NATIVE_BBOX_TM06,
            header_epsg_codes=header_epsg_codes,
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )
    async with db_session_maker() as session:
        mission = await session.get(models.SurveyMission, discovery_env["mission"].id)
        mission.implicit_crs = implicit_crs
        session.add(mission)
        await session.commit()

    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    (record,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    assert expected_crs in record.description
    minx, miny, maxx, maxy = to_shape(record.bbox_4326).bounds
    assert -8.2 < minx <= maxx < -8.0
    assert 39.6 < miny <= maxy < 39.8


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_heals_tracked_record_without_bbox(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    # a record discovered while the mission's CRS was still the 4326 default has no
    # bbox, and gets one from a re-run once the mission has a projected CRS
    mission_root = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH
    for name in ("drawn.tif", "healed.tif"):
        target = mission_root / "s01" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"content is irrelevant, dispatch is faked")
    drawn = record_schemas.SurveyRelatedRecordCreate.model_validate(
        _record_to_create(discovery_env, "s01/drawn.tif").model_dump()
        | {"bbox_4326": _DRAWN_BBOX_WKT}
    )
    without_bbox = _record_to_create(discovery_env, "s01/healed.tif")
    # an update drops the data assets and relations its payload does not restate
    without_bbox = without_bbox.model_copy(
        update={
            # typed by hand, and replaced by the extracted ones
            "temporal_extent_begin": dt.date(2020, 1, 1),
            "temporal_extent_end": dt.date(2020, 1, 2),
            "assets": [
                *without_bbox.assets,
                # outside every configuration's pattern
                record_schemas.DataRecordAssetCreate(
                    id=identifiers.RecordAssetId(uuid.uuid4()),
                    name="notes",
                    relative_path="notes/healed.txt",
                ),
            ],
            "related_records": [
                record_schemas.RelatedRecordCreate(
                    related_record_id=drawn.id, relationship="derived from"
                )
            ],
        }
    )
    for to_create in (drawn, without_bbox):
        await _create_record_without_discovery(db_session_maker, admin_user, to_create)
    async with db_session_maker() as session:
        mission = await session.get(models.SurveyMission, discovery_env["mission"].id)
        mission.implicit_crs = 3763
        session.add(mission)
        await session.commit()
    extraction_calls = []

    def fake_dispatch(path):
        extraction_calls.append(path)
        return extractor_schemas.SegyMetadata(
            driver="SEG-Y",
            bbox_native=_NATIVE_BBOX_TM06,
            temporal_extent_begin=dt.date(2024, 9, 28),
            temporal_extent_end=dt.date(2024, 9, 29),
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )

    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    # a record that has a bbox is not read again
    assert extraction_calls == [str(mission_root / "s01/healed.tif")]
    records = {
        r.id: r
        for r in await _get_mission_records(
            db_session_maker, discovery_env["mission"].id
        )
    }
    healed = records[without_bbox.id]
    minx, miny, maxx, maxy = to_shape(healed.bbox_4326).bounds
    assert -8.2 < minx <= maxx < -8.0
    assert 39.6 < miny <= maxy < 39.8
    assert (
        "CRS: ETRS89 / Portugal TM06 (EPSG:3763, from the survey mission)."
        in healed.description
    )
    assert healed.temporal_extent_begin == dt.date(2024, 9, 28)
    assert healed.temporal_extent_end == dt.date(2024, 9, 29)
    assert healed.validation_result["is_valid"] is True
    assets = await _get_record_assets(db_session_maker, without_bbox.id)
    assert sorted(a.relative_path for a in assets) == [
        "notes/healed.txt",
        "s01/healed.tif",
    ]
    async with db_session_maker() as session:
        links = (
            await session.exec(sqlmodel.select(models.SurveyRelatedRecordSelfLink))
        ).all()
    assert [(link.subject_id, link.related_to_id, link.relation) for link in links] == [
        (without_bbox.id, drawn.id, "derived from")
    ]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "implicit_crs, bbox_native, status, expected_extractions",
    [
        pytest.param(
            3763,
            None,
            constants.SurveyRelatedRecordStatus.DRAFT,
            1,
            id="still no bbox",
        ),
        pytest.param(
            3763,
            _NATIVE_BBOX_TM06,
            constants.SurveyRelatedRecordStatus.UNDER_DERIVATION,
            1,
            id="record busy",
        ),
        pytest.param(
            4326,
            _NATIVE_BBOX_TM06,
            constants.SurveyRelatedRecordStatus.DRAFT,
            0,
            id="geographic mission crs",
        ),
    ],
)
async def test_discovery_heal_writes_nothing(
    db_session_maker,
    admin_user,
    discovery_env,
    monkeypatch,
    implicit_crs,
    bbox_native,
    status,
    expected_extractions,
):
    target = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/line.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content is irrelevant, dispatch is faked")
    to_create = _record_to_create(discovery_env, "s01/line.tif")
    await _create_record_without_discovery(db_session_maker, admin_user, to_create)
    async with db_session_maker() as session:
        # found twice, by overlapping configurations, the file is never read twice
        await discovery_commands.create_asset_discovery_configuration(
            session,
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
                name="any tif",
                relative_path_regexp=r".*\.tif",
                media_type="image/tiff",
                generate_previews=True,
                workflow_stage_id=identifiers.WorkflowStageId(
                    discovery_env["configuration"].workflow_stage_id
                ),
                dataset_category_id=identifiers.DatasetCategoryId(
                    discovery_env["configuration"].dataset_category_id
                ),
            ),
        )
        mission = await session.get(models.SurveyMission, discovery_env["mission"].id)
        mission.implicit_crs = implicit_crs
        record = await session.get(models.SurveyRelatedRecord, to_create.id)
        record.status = status
        session.add_all((mission, record))
        await session.commit()
    extraction_calls = []

    def fake_dispatch(path):
        extraction_calls.append(path)
        return extractor_schemas.SegyMetadata(
            driver="SEG-Y",
            bbox_native=bbox_native,
            temporal_extent_begin=dt.date(2024, 9, 28),
            temporal_extent_end=dt.date(2024, 9, 29),
        )

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", fake_dispatch
    )

    collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    assert len(extraction_calls) == expected_extractions
    (record,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    assert record.bbox_4326 is None
    assert record.description == "A record created by hand"
    assert record.temporal_extent_begin is None
    assert record.temporal_extent_end is None
    assert [e.succeeded for e in _ended_events(collector)] == [True]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_enqueues_one_mission_derivation(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_mission_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )
    # the mission's directory is not in the archive yet, so discovery fails
    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    assert enqueued == []

    for name in ("first.tif", "second.tif"):
        _write_geotiff(
            discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01" / name
        )
    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    # a single derivation for the whole mission, however many files were found
    assert [e["raw_survey_mission_id"] for e in enqueued] == [
        str(discovery_env["mission"].id)
    ]

    # every discovery enqueues it again, it is the derivation which skips the
    # records that already have previews
    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    assert len(enqueued) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mission_previews_are_derived_for_missing_only(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    mission_root = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH
    for name in ("first.tif", "second.tif", "derived.tif"):
        _write_geotiff(mission_root / "s01/s02" / name)
    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    records = {
        r.name: r
        for r in await _get_mission_records(
            db_session_maker, discovery_env["mission"].id
        )
    }
    async with db_session_maker() as session:
        session.add(
            models.RecordAsset(
                id=uuid.uuid4(),
                survey_related_record_id=records["derived.tif"].id,
                name="derived.tif preview",
                description="",
                media_type="image/webp",
                asset_type=[constants.AssetType.THUMBNAIL, constants.AssetType.PREVIEW],
                data=b"fake webp payload",
            )
        )
        await session.commit()
        collected = await preview_ops.collect_survey_mission_records_missing_previews(
            session, identifiers.SurveyMissionId(discovery_env["mission"].id)
        )
    missing = sorted(str(records[name].id) for name in ("first.tif", "second.tif"))
    # derived.tif already has a preview, so it is left out
    assert sorted(str(record_id) for record_id in collected) == missing

    enqueued = []
    monkeypatch.setattr(
        preview_tasks.generate_record_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )
    # unwrapped, as the actors only run inside a worker
    await inspect.unwrap(preview_tasks.generate_mission_previews.fn)(
        raw_request_id=str(uuid.uuid4()),
        raw_survey_mission_id=str(discovery_env["mission"].id),
        raw_initiator=json.dumps(dataclasses.asdict(admin_user)),
        settings=discovery_env["settings"],
    )
    # one derivation per record which is missing its previews
    assert sorted(e["raw_survey_related_record_id"] for e in enqueued) == missing

    # the test settings have no message broker to dispatch the events through
    monkeypatch.setattr(
        discovery_env["settings"], "_event_dispatcher", _EventCollector()
    )

    def fake_dispatch(path, implicit_epsg_code):
        return deriver_schemas.DerivedPreview(
            image=b"fake webp payload", bounds_4326=(-8.2, 39.6, -8.1, 39.7)
        )

    monkeypatch.setattr(preview_ops.deriver_dispatch, "dispatch_deriver", fake_dispatch)

    # and each message runs the record derivation as it was sent
    for message in enqueued:
        await inspect.unwrap(preview_tasks.generate_record_previews.fn)(
            **message, settings=discovery_env["settings"]
        )
    for name in ("first.tif", "second.tif"):
        assets = await _get_record_assets(db_session_maker, records[name].id)
        assert [a.asset_type for a in assets if a.relative_path is None] == [
            [constants.AssetType.THUMBNAIL, constants.AssetType.PREVIEW]
        ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_previews_skip_a_record_whose_status_moved(
    db_session_maker, admin_user, discovery_env, monkeypatch, caplog
):
    mission_root = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH
    for name in ("untouched.tif", "moved.tif"):
        _write_geotiff(mission_root / "s01/s02" / name)
    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    records = {
        r.name: r
        for r in await _get_mission_records(
            db_session_maker, discovery_env["mission"].id
        )
    }

    def fake_dispatch(path, implicit_epsg_code):
        return deriver_schemas.DerivedPreview(
            image=b"fake webp payload", bounds_4326=(-8.2, 39.6, -8.1, 39.7)
        )

    monkeypatch.setattr(preview_ops.deriver_dispatch, "dispatch_deriver", fake_dispatch)

    async with db_session_maker() as session:
        untouched = await record_queries.get_survey_related_record(
            session, records["untouched.tif"].id
        )
        moved = await record_queries.get_survey_related_record(
            session, records["moved.tif"].id
        )
        # another derivation takes hold of moved.tif after it was fetched
        async with db_session_maker() as concurrent_session:
            concurrent = await concurrent_session.get(
                models.SurveyRelatedRecord, moved.id
            )
            concurrent.status = constants.SurveyRelatedRecordStatus.UNDER_DERIVATION
            concurrent_session.add(concurrent)
            await concurrent_session.commit()
        with caplog.at_level(logging.WARNING, logger=preview_ops.logger.name):
            for record in (untouched, moved):
                await preview_ops.generate_record_previews(
                    request_id=identifiers.RequestId(uuid.uuid4()),
                    survey_related_record=record,
                    initiator=admin_user,
                    session=session,
                    event_dispatcher=_EventCollector(),
                    settings=discovery_env["settings"],
                )

    untouched_assets = await _get_record_assets(db_session_maker, untouched.id)
    moved_assets = await _get_record_assets(db_session_maker, moved.id)
    async with db_session_maker() as session:
        untouched_status = (
            await session.get(models.SurveyRelatedRecord, untouched.id)
        ).status
        moved_status = (await session.get(models.SurveyRelatedRecord, moved.id)).status
    # the untouched record gets its preview, and was only held under derivation
    # while the preview was stored
    assert [a.asset_type for a in untouched_assets if a.relative_path is None] == [
        [constants.AssetType.THUMBNAIL, constants.AssetType.PREVIEW]
    ]
    assert untouched_status == records["untouched.tif"].status
    # the moved one is skipped with a warning: its preview is not stored, nor is
    # the status set by the other derivation undone
    assert any("changed status" in r.message for r in caplog.records)
    assert [a.asset_type for a in moved_assets] == [[constants.AssetType.DATA]]
    assert moved_status == constants.SurveyRelatedRecordStatus.UNDER_DERIVATION


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ineligible_by",
    ["configuration flag", "no matching configuration", "first matching configuration"],
)
async def test_record_previews_need_a_configuration_that_generates_them(
    db_session_maker,
    admin_user,
    discovery_env,
    monkeypatch,
    ineligible_by,
    bootstrap_dataset_categories,
    bootstrap_workflow_stages,
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )
    (discovered,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    async with db_session_maker() as session:
        configuration = await session.get(
            models.AssetDiscoveryConfiguration, discovery_env["configuration"].id
        )
        match ineligible_by:
            case "configuration flag":
                configuration.generate_previews = False
                session.add(configuration)
                await session.commit()
            case "no matching configuration":
                configuration.relative_path_regexp = r"s02/.*\.tif"
                session.add(configuration)
                await session.commit()
            case "first matching configuration":
                await discovery_commands.create_asset_discovery_configuration(
                    session,
                    discovery_schemas.AssetDiscoveryConfigurationCreate(
                        id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
                        # sorts before the test configuration, so it decides
                        name="a tif without previews",
                        relative_path_regexp=r"s01/.*\.tif",
                        media_type="image/tiff",
                        generate_previews=False,
                        workflow_stage_id=identifiers.WorkflowStageId(
                            bootstrap_workflow_stages[0].id
                        ),
                        dataset_category_id=identifiers.DatasetCategoryId(
                            bootstrap_dataset_categories[0].id
                        ),
                    ),
                )

    def fake_dispatch(path, implicit_epsg_code):
        return deriver_schemas.DerivedPreview(
            image=b"fake webp payload", bounds_4326=(-8.2, 39.6, -8.1, 39.7)
        )

    monkeypatch.setattr(preview_ops.deriver_dispatch, "dispatch_deriver", fake_dispatch)

    async with db_session_maker() as session:
        await preview_ops.generate_record_previews(
            request_id=identifiers.RequestId(uuid.uuid4()),
            survey_related_record=await record_queries.get_survey_related_record(
                session, discovered.id
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
            settings=discovery_env["settings"],
        )

    assets = await _get_record_assets(db_session_maker, discovered.id)
    assert [a.asset_type for a in assets] == [[constants.AssetType.DATA]]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_previews_of_a_record_created_by_hand(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/grid.tif"
    )
    to_create = _record_to_create(discovery_env, "s01/grid.tif")
    await _create_record_without_discovery(db_session_maker, admin_user, to_create)

    def fake_dispatch(path, implicit_epsg_code):
        return deriver_schemas.DerivedPreview(
            image=b"fake webp payload", bounds_4326=(-8.2, 39.6, -8.1, 39.7)
        )

    monkeypatch.setattr(preview_ops.deriver_dispatch, "dispatch_deriver", fake_dispatch)

    collector = _EventCollector()
    async with db_session_maker() as session:
        await preview_ops.generate_record_previews(
            request_id=identifiers.RequestId(uuid.uuid4()),
            survey_related_record=await record_queries.get_survey_related_record(
                session, to_create.id
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=collector,
            settings=discovery_env["settings"],
        )

    assets = await _get_record_assets(db_session_maker, to_create.id)
    assert sorted(a.asset_type for a in assets) == [
        [constants.AssetType.DATA],
        [constants.AssetType.THUMBNAIL, constants.AssetType.PREVIEW],
    ]
    # a derivation event rather than a modification, which list pages would show
    assert [
        (e.resource_id, e.parent_resource_id)
        for e in collector.events
        if isinstance(e, event_schemas.DerivationEvent)
    ] == [(str(to_create.id), str(discovery_env["mission"].id))]
    assert not any(
        isinstance(e, event_schemas.ResourceModificationEvent) for e in collector.events
    )

    # already derived, so a run that skips derived records leaves it alone
    collector = _EventCollector()
    async with db_session_maker() as session:
        await preview_ops.generate_record_previews(
            request_id=identifiers.RequestId(uuid.uuid4()),
            survey_related_record=await record_queries.get_survey_related_record(
                session, to_create.id
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=collector,
            settings=discovery_env["settings"],
            skip_if_derived=True,
        )
    assert collector.events == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_create_extracts_extents(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    data_file = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/sub/x.tif"
    _write_geotiff(data_file)
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_record_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )

    async with db_session_maker() as session:
        await discovery_ops.create_manual_survey_related_record(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_create=_record_to_create(discovery_env, "s01/sub/x.tif"),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
            settings=discovery_env["settings"],
        )

    (record,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    minx, miny, maxx, maxy = to_shape(record.bbox_4326).bounds
    assert -8.2 < minx <= maxx < -8.0
    assert 39.6 < miny <= maxy < 39.8
    # sent without a bbox: valid only if the extracted one came before validation
    assert record.validation_result["is_valid"] is True
    # the text discovery stores, in place of the one typed in the payload
    extracted = discovery_ops.extractor_dispatch.dispatch_extractor(str(data_file))
    assert record.description == extracted.describe()
    assert [e["raw_survey_related_record_id"] for e in enqueued] == [str(record.id)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_update_new_path_reextracts(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "other/x.tif"
    )
    to_create = _record_to_create(discovery_env, "s01/grid.tif")
    await _create_record_without_discovery(db_session_maker, admin_user, to_create)
    asset_id = to_create.assets[0].id
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_record_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )

    await _update_record_by_hand(
        db_session_maker,
        admin_user,
        discovery_env["settings"],
        to_create.id,
        record_schemas.SurveyRelatedRecordUpdate(
            bbox_4326=_DRAWN_BBOX_WKT,
            assets=[
                record_schemas.DataRecordAssetUpdate(
                    id=asset_id, relative_path="other/x.tif"
                )
            ],
        ),
    )

    (record,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    # the extracted bbox overrides the drawn one
    minx, miny, maxx, maxy = to_shape(record.bbox_4326).bounds
    assert -8.2 < minx <= maxx < -8.0
    assert 39.6 < miny <= maxy < 39.8
    assert len(enqueued) == 1

    # same data file, so the pipeline does not run and the drawn bbox stays
    await _update_record_by_hand(
        db_session_maker,
        admin_user,
        discovery_env["settings"],
        to_create.id,
        record_schemas.SurveyRelatedRecordUpdate(
            name="Renamed record",
            bbox_4326=_DRAWN_BBOX_WKT,
            assets=[
                record_schemas.DataRecordAssetUpdate(
                    id=asset_id, relative_path="other/x.tif"
                )
            ],
        ),
    )

    (record,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    assert to_shape(record.bbox_4326).bounds == pytest.approx((-9, 38, -8.9, 38.1))
    assert len(enqueued) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_manual_update_failed_extraction_keeps_extents(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    to_create = _record_to_create(discovery_env, "other/old.tif")
    await _create_record_without_discovery(db_session_maker, admin_user, to_create)

    def failing_dispatch(path):
        raise RuntimeError("unreadable file")

    monkeypatch.setattr(
        discovery_ops.extractor_dispatch, "dispatch_extractor", failing_dispatch
    )
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_record_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )

    await _update_record_by_hand(
        db_session_maker,
        admin_user,
        discovery_env["settings"],
        to_create.id,
        record_schemas.SurveyRelatedRecordUpdate(
            description="A description typed by hand",
            bbox_4326=_DRAWN_BBOX_WKT,
            temporal_extent_begin=dt.date(2024, 9, 28),
            temporal_extent_end=dt.date(2024, 9, 29),
            assets=[
                record_schemas.DataRecordAssetUpdate(
                    id=to_create.assets[0].id, relative_path="s01/broken.tif"
                )
            ],
        ),
    )

    (record,) = await _get_mission_records(
        db_session_maker, discovery_env["mission"].id
    )
    assert to_shape(record.bbox_4326).bounds == pytest.approx((-9, 38, -8.9, 38.1))
    assert record.temporal_extent_begin == dt.date(2024, 9, 28)
    assert record.temporal_extent_end == dt.date(2024, 9, 29)
    assert record.description == "A description typed by hand"
    assert len(enqueued) == 1
