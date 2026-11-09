"""Integration tests for mission discovery with metadata extraction, for the
derivation of previews which it kicks off and for the same pipeline run over
records created or edited by hand.

These run against the test database and a fake archive built under tmp_path.
GDAL is required to build the synthetic fixture files; the module self-skips
where it is unavailable.
"""

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
                root_path="",
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


def _record_to_create(
    discovery_env, relative_path, asset_discovery_configuration_id=None
):
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
        asset_discovery_configuration_id=asset_discovery_configuration_id,
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


@pytest.mark.parametrize(
    "relative_path_regexp, relative_path, expected",
    [
        pytest.param(r"s01/.*\.tif", "s01/a/b/x.tif", True, id="any depth"),
        pytest.param(r"s01/.*\.tif", "s02/s01/x.tif", False, id="fixed prefix"),
        pytest.param(r"s01/.*\.tif", "s01/x.tif.aux.xml", False, id="anchored name"),
        pytest.param(r".*_Data/.*\.kmall", "02_Data/x/f.kmall", True, id="directory"),
        pytest.param(r".*_Data/.*\.kmall", "f.kmall", False, id="missing directory"),
        pytest.param("s01/grid.tif", "s01/grid.tif", True, id="literal"),
        pytest.param(r"/s01/.*\.tif", "s01/x.tif", True, id="leading slash"),
        pytest.param(r"s01/(.*\.tif", "s01/x.tif", False, id="invalid regexp"),
    ],
)
def test_path_matches_discovery_pattern(relative_path_regexp, relative_path, expected):
    assert (
        discovery_ops.path_matches_discovery_pattern(
            relative_path_regexp, relative_path
        )
        is expected
    )


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
    assert record.asset_discovery_configuration_id == discovery_env["configuration"].id
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
    # as if the record had been discovered before the configuration was stored on it
    async with db_session_maker() as session:
        record = await session.get(models.SurveyRelatedRecord, first_records[0].id)
        record.asset_discovery_configuration_id = None
        session.add(record)
        await session.commit()
    second_collector = await _run_discovery(
        db_session_maker,
        discovery_env["mission"].id,
        discovery_env["settings"],
        admin_user,
    )

    records = await _get_mission_records(db_session_maker, discovery_env["mission"].id)
    assert len(records) == 1
    assert records[0].id == first_records[0].id
    # the re-run links the already tracked record to its configuration
    assert (
        records[0].asset_discovery_configuration_id == discovery_env["configuration"].id
    )
    # dedup runs BEFORE extraction, so the second run must not extract at all
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
@pytest.mark.parametrize("ineligible_by", ["configuration flag", "no configuration"])
async def test_record_previews_need_a_configuration_that_generates_them(
    db_session_maker, admin_user, discovery_env, monkeypatch, ineligible_by
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
        if ineligible_by == "configuration flag":
            configuration = await session.get(
                models.AssetDiscoveryConfiguration, discovery_env["configuration"].id
            )
            configuration.generate_previews = False
            session.add(configuration)
        else:
            record = await session.get(models.SurveyRelatedRecord, discovered.id)
            record.asset_discovery_configuration_id = None
            session.add(record)
        await session.commit()

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
async def test_manual_create_adopts_config_and_extracts_extents(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    data_file = discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "s01/sub/x.tif"
    _write_geotiff(data_file)
    async with db_session_maker() as session:
        # matches the path as well, and comes first by name
        first_by_name = await discovery_commands.create_asset_discovery_configuration(
            session,
            discovery_schemas.AssetDiscoveryConfigurationCreate(
                id=identifiers.AssetDiscoveryConfId(uuid.uuid4()),
                name="another tif",
                relative_path_regexp=r"s01/sub/.*\.tif",
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
    assert record.asset_discovery_configuration_id == first_by_name.id
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
async def test_manual_update_new_path_readopts_and_reextracts(
    db_session_maker, admin_user, discovery_env, monkeypatch
):
    _write_geotiff(
        discovery_env["archive_root"] / _MISSION_RELATIVE_PATH / "other/x.tif"
    )
    to_create = _record_to_create(
        discovery_env, "s01/grid.tif", discovery_env["configuration"].id
    )
    await _create_record_without_discovery(db_session_maker, admin_user, to_create)
    asset_id = to_create.assets[0].id
    enqueued = []
    monkeypatch.setattr(
        discovery_ops.preview_tasks.generate_record_previews,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )

    # no configuration matches the new path
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
    assert record.asset_discovery_configuration_id is None
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
    assert record.asset_discovery_configuration_id == discovery_env["configuration"].id
    assert to_shape(record.bbox_4326).bounds == pytest.approx((-9, 38, -8.9, 38.1))
    assert record.temporal_extent_begin == dt.date(2024, 9, 28)
    assert record.temporal_extent_end == dt.date(2024, 9, 29)
    assert record.description == "A description typed by hand"
    assert len(enqueued) == 1
