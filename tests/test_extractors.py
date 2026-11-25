"""Metadata extraction from survey files

When survey files are discovered in the archive, their metadata is read from the files
themselves: the bounding box, the temporal extent, the coordinate reference system and
format-specific details for GeoTIFF and XYZ rasters, XYZ point clouds, shapefiles,
KMALL, SEG-Y and Teledyne PDS files. Damaged or implausible content is skipped or
rejected rather than recorded as incorrect metadata.
"""

# Unit tests for the metadata extractors package.
#
# Pure functions, no DB: these run by default (no marker). GDAL is required; the
# module self-skips where it is unavailable. Everything is exercised against
# synthetic files built in-test, so the suite needs no sample-data archive.

import datetime as dt
import json
import logging
import math
import struct
import typing
from pathlib import Path

import pytest

pytest.importorskip("osgeo")

from osgeo import (
    gdal,
    ogr,
    osr,
)

from seis_lab_data import constants
from seis_lab_data.tasks.extractors import (
    dispatch,
    kmall,
    schemas,
    xyz,
)
from seis_lab_data.tasks.extractors.gdal_raster import extract_raster_metadata
from seis_lab_data.tasks.extractors.gdal_vector import extract_vector_metadata
from seis_lab_data.tasks.extractors.kmall import (
    collect_position_fixes,
    extract_kmall_metadata,
)
from seis_lab_data.tasks.extractors.pds import extract_pds_metadata
from seis_lab_data.tasks.extractors.segy import extract_segy_metadata

gdal.UseExceptions()

# EPSG:3763 (ETRS89 / Portugal TM06); coordinates near its false origin land in
# central Portugal, so projected bboxes fall in a checkable lon/lat window.
_PT_TM06 = 3763
_POINTS = [(0.0, 0.0), (1000.0, 1000.0), (2000.0, 500.0)]


def _srs(epsg: int) -> osr.SpatialReference:
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    return srs


@pytest.fixture(scope="session")
def synthetic_geotiff(tmp_path_factory):
    """Write a 10x10 single-band GeoTIFF in PT-TM06/ETRS89, filled with ones and with a
    nodata value.
    """
    path = tmp_path_factory.mktemp("raster") / "grid.tif"
    ds = gdal.GetDriverByName("GTiff").Create(str(path), 10, 10, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((0.0, 10.0, 0.0, 2000.0, 0.0, -10.0))
    ds.SetProjection(_srs(_PT_TM06).ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    band.Fill(1.0)
    ds = None
    return path


@pytest.fixture(scope="session")
def synthetic_xyz(tmp_path_factory):
    """Write a 3x3 grid of XYZ points with unit spacing, without coordinate reference
    system.
    """
    path = tmp_path_factory.mktemp("xyz") / "grid.xyz"
    lines = [f"{x} {y} {x + y}" for y in range(3) for x in range(3)]
    path.write_text("\n".join(lines) + "\n")
    return path


def _write_shapefile(path, srs):
    driver = ogr.GetDriverByName("ESRI Shapefile")
    ds = driver.CreateDataSource(str(path))
    layer = ds.CreateLayer("points", srs=srs, geom_type=ogr.wkbPoint)
    for x, y in _POINTS:
        feature = ogr.Feature(layer.GetLayerDefn())
        geom = ogr.Geometry(ogr.wkbPoint)
        geom.AddPoint(x, y)
        feature.SetGeometry(geom)
        layer.CreateFeature(feature)
        feature = None
    ds = None


@pytest.fixture(scope="session")
def synthetic_shapefile(tmp_path_factory):
    """Write a point shapefile in PT-TM06/ETRS89, with its `.prj` file."""
    path = tmp_path_factory.mktemp("vector") / "points.shp"
    _write_shapefile(path, _srs(_PT_TM06))
    return path


@pytest.fixture(scope="session")
def synthetic_shapefile_no_prj(tmp_path_factory):
    """Write a point shapefile without a `.prj` file, hence without coordinate reference
    system.
    """
    path = tmp_path_factory.mktemp("vector_noprj") / "points.shp"
    _write_shapefile(path, None)
    return path


@pytest.fixture(scope="session")
def broken_vector(tmp_path_factory):
    """Write a point shapefile without its `.shx` index, which GDAL fails to open."""
    # A valid shapefile with its .shx removed: reproduces the real prr_eolicas
    # "missing .shx" condition, which GDAL refuses to open (SHAPE_RESTORE_SHX
    # defaults to NO) -> RuntimeError.
    path = tmp_path_factory.mktemp("broken") / "points.shp"
    _write_shapefile(path, _srs(_PT_TM06))
    path.with_suffix(".shx").unlink()
    return path


def test_raster_metadata_fields(synthetic_geotiff):
    """For a GeoTIFF raster, the extracted metadata holds its format, dimensions, band
    count, pixel size, no-data value and coordinate reference system, with its bounding
    box both in the native coordinates and in longitude and latitude.
    """
    result = extract_raster_metadata(synthetic_geotiff)

    assert isinstance(result, schemas.RasterMetadata)
    assert result.driver == "GTiff"
    assert result.width == 10
    assert result.height == 10
    assert result.band_count == 1
    assert result.pixel_size_x == 10.0
    assert result.pixel_size_y == -10.0
    assert result.nodata == -9999.0
    assert result.epsg == _PT_TM06
    assert "TM06" in result.crs_name

    assert result.bbox_native is not None
    minx, miny, maxx, maxy = result.bbox_native
    assert minx < maxx and miny < maxy

    assert result.bbox_4326 is not None
    lon_min, lat_min, lon_max, lat_max = result.bbox_4326
    assert -10.0 < lon_min <= lon_max < -6.0
    assert 36.0 < lat_min <= lat_max < 43.0


def test_xyz_raster(synthetic_xyz):
    """For a regular XYZ grid without coordinate reference system information, the
    dimensions and the bounding box in native coordinates are extracted, and no bounding
    box in longitude and latitude is produced.
    """
    result = extract_raster_metadata(synthetic_xyz)

    assert result.driver == "XYZ"
    assert result.width == 3
    assert result.height == 3
    # No .prj alongside an XYZ grid: no CRS, native bbox only.
    assert result.epsg is None
    assert result.bbox_native is not None
    assert result.bbox_4326 is None


def test_vector_metadata_fields(synthetic_shapefile):
    """For a shapefile, the extracted metadata holds its format, layer count, feature
    count, geometry type and coordinate reference system, with a correctly ordered
    bounding box both in native coordinates and in longitude and latitude.
    """
    result = extract_vector_metadata(synthetic_shapefile)

    assert isinstance(result, schemas.VectorMetadata)
    assert result.driver == "ESRI Shapefile"
    assert result.layer_count == 1
    assert result.feature_count == 3
    assert "Point" in result.geometry_type
    assert result.epsg == _PT_TM06

    assert result.bbox_native is not None
    minx, miny, maxx, maxy = result.bbox_native
    # Reorder trap: OGR GetExtent returns (minx, maxx, miny, maxy). If it were stored
    # verbatim, miny would be 2000 and this assertion would fail.
    assert minx < maxx
    assert miny < maxy

    assert result.bbox_4326 is not None
    lon_min, lat_min, lon_max, lat_max = result.bbox_4326
    assert -10.0 < lon_min <= lon_max < -6.0
    assert 36.0 < lat_min <= lat_max < 43.0


def test_vector_without_prj(synthetic_shapefile_no_prj):
    """For a shapefile without a projection file, the feature count and the bounding box
    in native coordinates are extracted, while no coordinate reference system and no
    bounding box in longitude and latitude are reported.
    """
    result = extract_vector_metadata(synthetic_shapefile_no_prj)

    assert result.epsg is None
    assert result.crs_name is None
    assert result.crs_wkt is None
    assert result.bbox_4326 is None
    assert result.bbox_native is not None
    assert result.feature_count == 3


def test_broken_vector_raises(broken_vector):
    """A shapefile missing its index file is reported as unreadable."""
    with pytest.raises(RuntimeError):
        extract_vector_metadata(broken_vector)


def test_dispatch_routes_raster(synthetic_geotiff):
    """A GeoTIFF file is recognised as a raster and its raster metadata is extracted."""
    assert isinstance(
        dispatch.dispatch_extractor(synthetic_geotiff), schemas.RasterMetadata
    )


def test_dispatch_routes_xyz(synthetic_xyz):
    """A regular XYZ grid file is recognised as a raster and its raster metadata is
    extracted.
    """
    result = dispatch.dispatch_extractor(synthetic_xyz)
    assert isinstance(result, schemas.RasterMetadata)
    assert result.driver == "XYZ"


# soundings: irregular x and y, which GDAL's XYZ driver rejects for not being a grid
_SOUNDINGS = [
    (10.5, 20.25, 1.0),
    (13.75, 18.5, 2.0),
    (11.0, 25.5, 1.5),
    (9.25, 21.0, 3),
]


def test_dispatch_routes_ungridded_xyz_to_the_point_cloud_extractor(tmp_path):
    """An XYZ file holding irregularly spaced soundings is recognised as a point cloud,
    with its file size, point count and native bounding box extracted, and its bounding
    box marked for placement using the coordinate reference system of the survey
    mission.
    """
    path = tmp_path / "soundings.xyz"
    path.write_text("".join(f"{x} {y} {z}\n" for x, y, z in _SOUNDINGS))

    result = dispatch.dispatch_extractor(path)

    assert isinstance(result, schemas.PointCloudMetadata)
    assert result.file_size_bytes == path.stat().st_size
    assert result.point_count == 4
    assert result.bbox_native == (9.25, 18.5, 13.75, 25.5)
    # no CRS in the file: placed by the survey mission's CRS, as an XYZ grid is
    assert result.bbox_4326 is None
    assert result.bbox_native_needing_crs == (9.25, 18.5, 13.75, 25.5)


def test_xyz_points_skip_a_header_and_accept_commas(tmp_path):
    """An XYZ point cloud with a header line and comma-separated values is read
    correctly, giving the right point count and bounding box.
    """
    path = tmp_path / "soundings.xyz"
    path.write_text(
        "Easting,Northing,Depth\n" + "".join(f"{x},{y},{z}\n" for x, y, z in _SOUNDINGS)
    )

    result = xyz.extract_xyz_points_metadata(path)

    assert result.point_count == 4
    assert result.bbox_native == (9.25, 18.5, 13.75, 25.5)


def test_xyz_points_of_a_large_file_are_sampled(tmp_path, monkeypatch):
    """For a large XYZ point cloud, only a fixed number of portions of the file are
    read, the bounding box is derived from those portions, and the point count is
    reported as an estimate close to the true count.
    """
    monkeypatch.setattr(xyz, "_SAMPLE_WINDOWS", 4)
    monkeypatch.setattr(xyz, "_SAMPLE_WINDOW_BYTES", 64)
    # 1000 rows of the same length, x rising along the file: the westernmost and
    # easternmost points are in the first and last windows, while a southernmost
    # point in the middle of the file lies between the windows and is missed
    rows = [
        f"{1000 + index} {4000 if index == 500 else 5000} 1.0" for index in range(1000)
    ]
    path = tmp_path / "soundings.xyz"
    path.write_text("\n".join(rows))
    read_sizes = []
    real_open = Path.open

    def recording_open(self, *args, **kwargs):
        fh = real_open(self, *args, **kwargs)
        real_read = fh.read

        def recording_read(size=-1):
            data = real_read(size)
            read_sizes.append(len(data))
            return data

        fh.read = recording_read
        return fh

    monkeypatch.setattr(Path, "open", recording_open)

    result = xyz.extract_xyz_points_metadata(path)

    assert read_sizes == [64] * 4
    assert result.bbox_native == (1000.0, 5000.0, 1999.0, 5000.0)
    assert result.point_count_estimated
    assert result.point_count == pytest.approx(1000, rel=0.05)


def test_xyz_points_of_a_small_file_are_counted(tmp_path):
    """A small XYZ point cloud is read in full, so its point count is exact and its
    bounding box covers every point, including one on a final line without a line break.
    """
    # read whole, its last line without a line break
    path = tmp_path / "soundings.xyz"
    path.write_text("\n".join(f"{x} {y} {z}" for x, y, z in _SOUNDINGS))

    result = xyz.extract_xyz_points_metadata(path)

    assert result.point_count == 4
    assert not result.point_count_estimated
    assert result.bbox_native == (9.25, 18.5, 13.75, 25.5)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "just some text\n",
        "1 2 3\n4 5\n",
        "1 2 3\n4 5 deep\n",
    ],
    ids=["empty", "no numbers", "ragged rows", "not a number"],
)
def test_xyz_points_reject_what_is_not_a_point_cloud(tmp_path, content):
    """Empty files, text without numbers, rows with missing values and rows with non-
    numeric values are rejected as not being XYZ point clouds.
    """
    path = tmp_path / "soundings.xyz"
    path.write_text(content)

    with pytest.raises(ValueError):
        xyz.extract_xyz_points_metadata(path)


def test_dispatch_routes_vector(synthetic_shapefile):
    """A shapefile is recognised as vector data, and its reported file size is that of
    the main file alone, excluding its companion files.
    """
    result = dispatch.dispatch_extractor(synthetic_shapefile)

    assert isinstance(result, schemas.VectorMetadata)
    # the size of the .shp file alone, without its sidecars
    assert result.file_size_bytes == synthetic_shapefile.stat().st_size


@pytest.mark.parametrize("suffix", [".shx", ".dbf", ".prj", ".cpg", ".qmd", ".sbn"])
def test_dispatch_ignores_sidecars(tmp_path, suffix):
    """Companion files of a shapefile, such as index, attribute and projection files,
    are not processed as data files of their own.
    """
    sidecar = tmp_path / f"points{suffix}"
    sidecar.write_bytes(b"\x00")
    assert dispatch.dispatch_extractor(sidecar) is None


def test_dispatch_unknown_extension(tmp_path):
    """A file of an unsupported type is skipped without producing metadata."""
    unknown = tmp_path / "notes.txt"
    unknown.write_text("hello")
    assert dispatch.dispatch_extractor(unknown) is None


def test_dispatch_directory_named_like_raster(tmp_path):
    """A directory whose name ends in a raster file extension is skipped rather than
    opened as a raster.
    """
    # A real directory named "F3_2022.tif" exists in the archive; it must not be opened.
    fake = tmp_path / "F3_2022.tif"
    fake.mkdir()
    assert dispatch.dispatch_extractor(fake) is None


def test_dispatch_big_file_logs(synthetic_geotiff, monkeypatch, caplog):
    """The extraction of metadata from a large raster file is recorded in the
    application log.
    """
    monkeypatch.setattr(dispatch, "_BIG_FILE_LOG_BYTES", 0)
    with caplog.at_level(logging.INFO, logger=dispatch.logger.name):
        result = dispatch.dispatch_extractor(synthetic_geotiff)
    assert isinstance(result, schemas.RasterMetadata)
    assert any("large raster" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    "metadata, expected",
    [
        pytest.param(
            schemas.SegyMetadata(
                driver="SEG-Y",
                file_size_bytes=7200,
                epsg=_PT_TM06,
                crs_name="ETRS89 / Portugal TM06",
                crs_from_mission=True,
                bbox_native=(-50000.0, 150000.0, -48000.0, 152000.0),
                bbox_4326=(-8.7, 40.0, -8.6, 40.1),
                temporal_extent_begin=dt.date(2024, 9, 28),
                temporal_extent_end=dt.date(2024, 9, 29),
                trace_count=3,
                samples_per_trace=4,
                sample_interval=250,
                sample_format="ieee-float32",
                coordinate_units="metres",
                coverage="partial",
                header_epsg_codes=(_PT_TM06,),
                sampled_positions=((-50000.0, 150000.0), (-48000.0, 152000.0)),
            ),
            {
                "driver": "SEG-Y",
                "file_size_bytes": 7200,
                "epsg": _PT_TM06,
                "crs_name": "ETRS89 / Portugal TM06",
                "crs_from_mission": True,
                "bbox_native": [-50000.0, 150000.0, -48000.0, 152000.0],
                "trace_count": 3,
                "samples_per_trace": 4,
                "sample_interval": 250,
                "sample_format": "ieee-float32",
                "coordinate_units": "metres",
                "coverage": "partial",
            },
            id="segy with partial coverage, placed by the mission's crs",
        ),
        pytest.param(
            schemas.RasterMetadata(
                driver="GTiff",
                file_size_bytes=1_500_000,
                epsg=_PT_TM06,
                crs_name="ETRS89 / Portugal TM06",
                crs_wkt='PROJCS["ETRS89 / Portugal TM06"]',
                bbox_native=(0.0, 1900.0, 100.0, 2000.0),
                bbox_4326=(-8.13, 39.66, -8.12, 39.67),
                width=10,
                height=10,
                band_count=1,
                pixel_size_x=10.0,
                pixel_size_y=-10.0,
                nodata=math.nan,
            ),
            {
                "type": "raster",
                "driver": "GTiff",
                "file_size_bytes": 1_500_000,
                "epsg": _PT_TM06,
                "crs_name": "ETRS89 / Portugal TM06",
                "bbox_native": [0.0, 1900.0, 100.0, 2000.0],
                "width": 10,
                "height": 10,
                "band_count": 1,
                "pixel_size_x": 10.0,
                "pixel_size_y": -10.0,
            },
            id="raster with a nan nodata",
        ),
        pytest.param(
            schemas.PointCloudMetadata(
                driver="XYZ",
                file_size_bytes=64_000,
                bbox_native=(1000.0, 5000.0, math.inf, 5000.0),
                point_count=1000,
                point_count_estimated=True,
            ),
            {
                "type": "point cloud",
                "driver": "XYZ",
                "file_size_bytes": 64_000,
                "point_count": 1000,
                "point_count_estimated": True,
            },
            id="estimated point cloud with an infinite native bbox",
        ),
    ],
)
def test_discovery_info(metadata, expected):
    """For SEG-Y files, rasters and point clouds, the metadata shown on a survey-related
    record's page omits default values, extents and internal details, and leaves out
    values that cannot be stored, such as undefined or infinite numbers.
    """
    info = metadata.get_discovery_info()

    assert info == expected
    # PostgreSQL rejects the NaN and Infinity that Python's JSON would write
    json.dumps(info, allow_nan=False)


def test_discovery_info_keys_are_the_metadata_fields():
    """Every metadata field extracted from a file is either shown on the survey-related
    record's page, shown as part of another item, or deliberately excluded from it.
    """
    # a field added to a metadata model must be shown on the record's page, in an
    # item of its own or in another's, or be kept off the page on purpose
    fields = set()
    for model in typing.get_args(schemas.ExtractionResult):
        fields |= set(model.model_fields)
    not_stored = {
        "crs_wkt",
        "bbox_4326",
        "temporal_extent_begin",
        "temporal_extent_end",
        "header_epsg_codes",
        "sampled_positions",
    }
    shown_in_the_item_of_another = {
        "epsg",
        "crs_from_mission",
        "height",
        "pixel_size_y",
        "point_count_estimated",
    }
    stored_but_not_shown = {"type", "coverage"}
    shown = {key.value for key in constants.DiscoveryInfoKey}

    assert shown | shown_in_the_item_of_another | stored_but_not_shown == (
        fields - not_stored
    ) | {"type"}


def test_bbox_native_needing_crs_when_file_declares_none():
    """When a file holds coordinates but declares no coordinate reference system, its
    bounding box is marked for placement using the coordinate reference system of the
    survey mission.
    """
    # the SEG-Y / XYZ case: coordinates, but nothing saying which CRS they are in
    metadata = schemas.SegyMetadata(bbox_native=(0.0, 1900.0, 100.0, 2000.0))
    assert metadata.bbox_native_needing_crs == (0.0, 1900.0, 100.0, 2000.0)


def test_bbox_native_needing_crs_is_none_when_epsg_is_known():
    """When a file declares an EPSG code, its bounding box is not marked for placement
    using the coordinate reference system of the survey mission.
    """
    metadata = schemas.SegyMetadata(bbox_native=(0.0, 1900.0, 100.0, 2000.0), epsg=3763)
    assert metadata.bbox_native_needing_crs is None


def test_bbox_native_needing_crs_is_none_when_only_wkt_is_known():
    """When a file describes its coordinate reference system without an EPSG code, its
    bounding box is not marked for placement using the coordinate reference system of
    the survey mission.
    """
    # AutoIdentifyEPSG fails on some archive files, leaving wkt as the only CRS
    metadata = schemas.SegyMetadata(
        bbox_native=(0.0, 1900.0, 100.0, 2000.0),
        crs_wkt='PROJCS["ETRS89 / Portugal TM06"]',
    )
    assert metadata.bbox_native_needing_crs is None


def test_bbox_native_needing_crs_is_none_when_already_projected():
    """When a bounding box in longitude and latitude is already known, the native
    bounding box is not marked for placement using the coordinate reference system of
    the survey mission.
    """
    metadata = schemas.SegyMetadata(
        bbox_native=(0.0, 1900.0, 100.0, 2000.0),
        bbox_4326=(-8.2, 39.6, -8.1, 39.7),
    )
    assert metadata.bbox_native_needing_crs is None


def test_bbox_native_needing_crs_is_none_without_coordinates():
    """A file without any coordinates has no bounding box to be placed using the
    coordinate reference system of the survey mission.
    """
    assert schemas.SegyMetadata().bbox_native_needing_crs is None


# 2024-09-28 18:48:31 UTC, matching the archive's EM712 line 0419
_KMALL_T0 = 1_727_549_311
_KMALL_HEADER = struct.Struct("<I4sBBHII")


def _kmall_datagram(dgm_type, time_sec, body=b""):
    total = _KMALL_HEADER.size + len(body) + 4
    header = _KMALL_HEADER.pack(total, dgm_type, 0, 0, 712, time_sec, 0)
    return header + body + struct.pack("<I", total)


def _kmall_position_body(lat, lon):
    # common part (8 bytes) + sensor data: two times, fix quality, lat/lon
    common = struct.pack("<HHHH", 8, 0, 0, 0)
    sensor = struct.pack("<IIf", 0, 0, 1.0) + struct.pack("<dd", lat, lon)
    return common + sensor


def _write_kmall(path, fixes, dgm_type=b"#SPO", cpo_fixes=()):
    datagrams = [_kmall_datagram(b"#SVT", _KMALL_T0)]
    for index, (lat, lon) in enumerate(fixes):
        datagrams.append(
            _kmall_datagram(dgm_type, _KMALL_T0 + index, _kmall_position_body(lat, lon))
        )
    for index, (lat, lon) in enumerate(cpo_fixes):
        datagrams.append(
            _kmall_datagram(b"#CPO", _KMALL_T0 + index, _kmall_position_body(lat, lon))
        )
    # a final datagram on the next day exercises the temporal range
    datagrams.append(_kmall_datagram(b"#SVT", _KMALL_T0 + 86400))
    path.write_bytes(b"".join(datagrams))


def test_kmall_metadata_fields(tmp_path):
    """For a KMALL file, the extracted metadata holds the echo sounder, the recording
    duration, the bounding box of its position fixes in longitude and latitude, and its
    temporal extent.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1), (40.6, -9.2)])

    result = extract_kmall_metadata(path)

    assert isinstance(result, schemas.KmallMetadata)
    assert result.driver == "KMALL"
    assert result.echo_sounder_id == 712
    assert result.duration_seconds == 86400
    assert result.epsg == 4326
    assert result.bbox_4326 == (-9.3, 40.5, -9.1, 40.7)
    assert result.bbox_native == result.bbox_4326
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def test_kmall_cpo_fallback(tmp_path):
    """For a KMALL file without primary position records, the bounding box is derived
    from its secondary position records.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1)], dgm_type=b"#CPO")

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 == (-9.3, 40.5, -9.1, 40.7)


def test_kmall_spo_takes_precedence_over_cpo(tmp_path):
    """For a KMALL file holding both primary and secondary position records, the
    bounding box is derived from the primary records only, ignoring diverging secondary
    positions.
    """
    # SPO is the primary source; a divergent CPO feed must be IGNORED, never
    # merged into the bbox
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1)], cpo_fixes=[(50.0, 5.0)])

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 == (-9.3, 40.5, -9.1, 40.7)


def test_kmall_collect_position_fixes_prefers_spo(tmp_path):
    """The positions collected from a KMALL file, used to draw its track, come from the
    primary position records when they are present.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1)], cpo_fixes=[(50.0, 5.0)])

    assert collect_position_fixes(path) == [(-9.3, 40.5), (-9.1, 40.7)]


def test_kmall_collect_position_fixes_falls_back_to_cpo(tmp_path):
    """When the primary position records of a KMALL file hold no usable position, its
    track is drawn from the secondary position records.
    """
    # a #SPO datagram is present but holds no usable fix, so #CPO takes over
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(0.0, 0.0)], cpo_fixes=[(40.5, -9.3), (40.7, -9.1)])

    assert collect_position_fixes(path) == [(-9.3, 40.5), (-9.1, 40.7)]


def test_kmall_short_position_body_skipped(tmp_path):
    """A truncated position record in a KMALL file is skipped, and the bounding box is
    derived from the remaining valid positions.
    """
    # a position datagram whose body ends before the lat/lon doubles must be
    # skipped without crashing
    short_body = struct.pack("<HHHH", 8, 0, 0, 0) + struct.pack("<IIf", 0, 0, 1.0)
    datagrams = [
        _kmall_datagram(b"#SPO", _KMALL_T0, short_body),
        _kmall_datagram(b"#SPO", _KMALL_T0 + 1, _kmall_position_body(40.6, -9.2)),
    ]
    path = tmp_path / "line.kmall"
    path.write_bytes(b"".join(datagrams))

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 == (-9.2, 40.6, -9.2, 40.6)


def test_kmall_without_positions(tmp_path):
    """A KMALL file without position records yields no bounding box and no coordinate
    reference system, while its temporal extent is still extracted.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(path, [])

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 is None
    assert result.epsg is None
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def test_kmall_skips_garbage_fixes(tmp_path):
    """Invalid positions in a KMALL file, such as out-of-range values, zero coordinates
    from signal dropouts and undefined values, are excluded from the bounding box.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(
        path,
        [
            (200.0, 5.0),  # out-of-range sentinel
            (0.0, 0.0),  # null-island GNSS dropout
            (math.nan, -9.2),
            (40.6, -9.2),  # the only valid fix
        ],
    )

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 == (-9.2, 40.6, -9.2, 40.6)


def test_kmall_truncated_tail_garbage(tmp_path):
    """A KMALL file ending in unreadable bytes still yields the bounding box and
    temporal extent of its readable part.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    with path.open("ab") as fh:
        fh.write(b"X" * 40)  # parses as an invalid header -> walk stops

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 == (-9.3, 40.5, -9.3, 40.5)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def test_kmall_truncated_tail_beyond_eof(tmp_path):
    """A KMALL file whose last record is cut short, as after an interruption of the
    acquisition, still yields the bounding box and temporal extent of its complete
    records.
    """
    # the realistic acquisition-crash shape: a well-formed header whose
    # num_bytes claims data beyond the end of the file
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    with path.open("ab") as fh:
        fh.write(_KMALL_HEADER.pack(99999, b"#MRZ", 0, 0, 712, _KMALL_T0 + 2, 0))

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 == (-9.3, 40.5, -9.3, 40.5)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def _write_sampled_kmall(path, fix_lon, sounding_bytes=30_000, count=200):
    """A KMALL file larger than the sampled read's windows, one second per datagram.

    Every fourth datagram is a #SPO fix at the longitude `fix_lon(index)` and a
    latitude rising along the file, the others are soundings whose payload holds
    `#` bytes and lengths, so that only a validated boundary is taken for one.
    """
    filler = (struct.pack("<I4s", 1000, b"#MRZ") + b"x#" * 16) * (sounding_bytes // 40)
    datagrams = []
    for index in range(count):
        if index % 4 == 0:
            body = _kmall_position_body(40.0 + index * 1e-4, fix_lon(index))
            datagrams.append(_kmall_datagram(b"#SPO", _KMALL_T0 + index, body))
        else:
            datagrams.append(
                _kmall_datagram(b"#MRZ", _KMALL_T0 + index, filler[:sounding_bytes])
            )
    content = b"".join(datagrams)
    assert len(content) > kmall._SAMPLE_WINDOWS * kmall._SAMPLE_WINDOW_BYTES
    path.write_bytes(content)


def test_kmall_sampled_read_covers_both_ends_and_the_middle(tmp_path):
    """For a large KMALL file, which is read in portions only, the bounding box and
    duration take into account the beginning, the middle and the end of the file.
    """
    # the easternmost fixes are only in the middle of the file, between the
    # windows at its ends
    path = tmp_path / "line.kmall"
    _write_sampled_kmall(
        path, lambda index: -9.3 if index < 20 else -9.2 if index >= 180 else -9.0
    )

    result = extract_kmall_metadata(path)

    west, south, east, north = result.bbox_4326
    assert (west, east) == (-9.3, -9.0)
    # the first and last fixes, from the windows at the ends of the file
    assert south == 40.0
    assert north == pytest.approx(40.0 + 196 * 1e-4)
    assert result.duration_seconds == 199
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)


def test_kmall_sampled_read_reads_windows_only(tmp_path, monkeypatch):
    """For a large KMALL file, only a fixed number of portions of the file are read."""
    path = tmp_path / "line.kmall"
    _write_sampled_kmall(path, lambda index: -9.3)
    read_sizes = []
    real_open = Path.open

    def recording_open(self, *args, **kwargs):
        fh = real_open(self, *args, **kwargs)
        real_read = fh.read

        def recording_read(size=-1):
            data = real_read(size)
            read_sizes.append(len(data))
            return data

        fh.read = recording_read
        return fh

    monkeypatch.setattr(Path, "open", recording_open)

    extract_kmall_metadata(path)

    assert read_sizes == [kmall._SAMPLE_WINDOW_BYTES] * kmall._SAMPLE_WINDOWS


def test_kmall_sampled_read_survives_a_truncated_tail(tmp_path):
    """A large KMALL file whose last record is cut short still yields a bounding box and
    a duration from the portions that can be read.
    """
    path = tmp_path / "line.kmall"
    _write_sampled_kmall(path, lambda index: -9.3)
    with path.open("ab") as fh:
        fh.write(_KMALL_HEADER.pack(99999, b"#MRZ", 0, 0, 712, _KMALL_T0 + 300, 0))

    result = extract_kmall_metadata(path)

    # the tail window yields nothing, the last middle window ends the extent
    assert result.bbox_4326[0] == -9.3
    assert 150 < result.duration_seconds < 199


def test_kmall_sampled_read_rejects_an_invalid_start(tmp_path):
    """A large file with a KMALL extension that does not begin with a valid KMALL record
    is rejected.
    """
    path = tmp_path / "line.kmall"
    _write_sampled_kmall(path, lambda index: -9.3)
    content = path.read_bytes()
    path.write_bytes(b"not a datagram" + content)

    with pytest.raises(ValueError):
        extract_kmall_metadata(path)


def test_kmall_garbage_raises(tmp_path):
    """A file with a KMALL extension that does not hold KMALL data is rejected."""
    path = tmp_path / "junk.kmall"
    path.write_bytes(b"this is definitely not a kmall file")
    with pytest.raises(ValueError):
        extract_kmall_metadata(path)


@pytest.mark.parametrize("content", [b"", b"tiny"])
def test_kmall_too_small_raises(tmp_path, content):
    """An empty or very small file with a KMALL extension is rejected."""
    # empty or sub-header files never enter the walk and must still raise
    path = tmp_path / "empty.kmall"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        extract_kmall_metadata(path)


@pytest.mark.parametrize("content", [b"", b"tiny"])
def test_kmall_collect_position_fixes_rejects_non_kmall(tmp_path, content):
    """Positions are not collected from an empty or very small file with a KMALL
    extension, which is rejected.
    """
    path = tmp_path / "empty.kmall"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        collect_position_fixes(path)


def test_dispatch_routes_kmall(tmp_path):
    """A KMALL file is recognised as such, and its metadata, including its file size, is
    extracted.
    """
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])

    result = dispatch.dispatch_extractor(path)

    assert isinstance(result, schemas.KmallMetadata)
    assert result.file_size_bytes == path.stat().st_size


# SEG-Y builders: tiny files with the real layout (3200-byte textual header +
# 400-byte binary header + fixed-length traces), big-endian by default. Day 272
# of 2024 is 2024-09-28, matching the archive's survey dates.
_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


def _segy_binary_header(ns, sample_format, interval, revision, n_ext, order):
    header = bytearray(400)
    struct.pack_into(order + "H", header, 16, interval)
    struct.pack_into(order + "H", header, 20, ns)
    struct.pack_into(order + "H", header, 24, sample_format)
    header[300] = revision
    struct.pack_into(order + "h", header, 304, n_ext)
    return bytes(header)


def _segy_trace(
    ns=4,
    bytes_per_sample=4,
    src=(0, 0),
    cdp=(0, 0),
    scalco=0,
    units=1,
    year=2024,
    day=272,
    hour=12,
    minute=30,
    second=15,
    order=">",
):
    header = bytearray(240)
    struct.pack_into(order + "h", header, 70, scalco)
    struct.pack_into(order + "ii", header, 72, *src)
    struct.pack_into(order + "H", header, 88, units)
    struct.pack_into(order + "HHHHH", header, 156, year, day, hour, minute, second)
    struct.pack_into(order + "ii", header, 180, *cdp)
    return bytes(header) + b"\x00" * (ns * bytes_per_sample)


def _write_segy(
    path,
    traces,
    ns=4,
    sample_format=5,
    interval=250,
    revision=1,
    n_ext=0,
    order=">",
    textual=b"",
    extended=b"",
    trailer=b"",
):
    path.write_bytes(
        textual.ljust(3200, b" ")
        + _segy_binary_header(ns, sample_format, interval, revision, n_ext, order)
        + extended
        + b"".join(traces)
        + trailer
    )


def test_segy_metres_path(tmp_path):
    """For a SEG-Y file with coordinates in metres and no declared coordinate reference
    system, the trace and sample information, the native bounding box, the track
    positions in sailing order and the temporal extent are extracted, without assuming
    any coordinate reference system.
    """
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-50000, 150000), day=272),
            _segy_trace(src=(-48000, 152000), day=273),
            _segy_trace(src=(-49000, 151000), day=272),
        ],
    )

    result = extract_segy_metadata(path)

    assert isinstance(result, schemas.SegyMetadata)
    assert result.driver == "SEG-Y"
    assert result.trace_count == 3
    assert result.samples_per_trace == 4
    assert result.sample_interval == 250
    assert result.sample_format == "ieee-float32"
    assert result.coordinate_units == "metres"
    assert result.coverage == "full"
    # undeclared projected metres: native bbox only, the CRS is never guessed
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)
    assert result.bbox_4326 is None
    assert result.epsg is None
    # in trace order, for the preview to draw the line as sailed
    assert result.sampled_positions == (
        (-50000.0, 150000.0),
        (-48000.0, 152000.0),
        (-49000.0, 151000.0),
    )
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def test_segy_geographic_degrees(tmp_path):
    """For a SEG-Y file with coordinates in degrees, the bounding box and track are
    given in longitude and latitude, and a trace whose coordinate units differ from
    those of the majority is left out.
    """
    # units=3 with scalco=-10000: raw ints are degrees times 10000
    # the stray metres trace is outvoted, so neither the box nor the track uses it
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-87500, 422300), scalco=-10000, units=3),
            _segy_trace(src=(-50000, 150000)),
            _segy_trace(src=(-87000, 422800), scalco=-10000, units=3),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.coordinate_units == "degrees"
    assert result.epsg == 4326
    assert result.crs_name == "WGS 84"
    assert result.bbox_4326 == (-8.75, 42.23, -8.7, 42.28)
    assert result.bbox_native == result.bbox_4326
    assert result.sampled_positions == ((-8.75, 42.23), (-8.7, 42.28))


def test_segy_geographic_arc_seconds(tmp_path):
    """For a SEG-Y file with coordinates in arc-seconds, the coordinates are converted
    to degrees of longitude and latitude.
    """
    # the real CW HAT.sgy shape: units=2, stationary, arc-seconds with a
    # negative scalar; -8.7385 deg is -31458.6 arc-seconds
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [_segy_trace(src=(-314586, 1520280), scalco=-10, units=2)],
    )

    result = extract_segy_metadata(path)

    assert result.coordinate_units == "arc-seconds"
    assert result.epsg == 4326
    lon_min, lat_min, lon_max, lat_max = result.bbox_4326
    assert lon_min == lon_max == pytest.approx(-8.7385)
    assert lat_min == lat_max == pytest.approx(42.23)


def test_segy_dms_units_skipped(tmp_path):
    """For a SEG-Y file with coordinates in packed degrees, minutes and seconds, no
    bounding box is produced, rather than an incorrect one.
    """
    # packed DDDMMSS.ss is never converted in v1; storing the packed integers
    # verbatim would fake a bbox
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(83030450, 421512), units=4)])

    result = extract_segy_metadata(path)

    assert result.coordinate_units == "dms"
    assert result.bbox_native is None
    assert result.bbox_4326 is None
    assert result.coverage == "full"


def test_segy_scalco_multiplies(tmp_path):
    """A positive coordinate scale factor in a SEG-Y file multiplies the stored
    coordinates.
    """
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(-5000, 15000), scalco=10)])

    result = extract_segy_metadata(path)

    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)


def test_segy_cdp_sentinel_fill_ignored(tmp_path):
    """Placeholder values filling the coordinate fields of SEG-Y traces are excluded
    from the bounding box.
    """
    # real archive traces carry INT32_MIN fill in the CDP fields while src holds
    # the good coordinates. The scalar matters: scaled by -10000 a sentinel
    # becomes -214748.36, well inside the plausible-metres range, so only the
    # sentinel guard itself keeps it out of the bbox
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-500000000, 1500000000), scalco=-10000),
            _segy_trace(src=(0, 0), cdp=(_INT32_MIN, _INT32_MIN), scalco=-10000),
            _segy_trace(src=(_INT32_MAX, _INT32_MAX), scalco=-10000),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)
    assert result.coverage == "full"


def test_segy_src_takes_precedence_over_cdp(tmp_path):
    """For a SEG-Y file holding both source and common depth point coordinates, the
    bounding box is derived from the source coordinates only.
    """
    # src is the primary source; a divergent cdp feed must be IGNORED, never
    # merged into the bbox (the KMALL SPO/CPO rule, applied to SEG-Y)
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-50000, 150000), cdp=(-90000, 190000)),
            _segy_trace(src=(-48000, 152000), cdp=(-91000, 191000)),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


def test_segy_cdp_fallback(tmp_path):
    """For SEG-Y traces without source coordinates, the bounding box is derived from the
    common depth point coordinates.
    """
    # chirp/Innomar/sbp populate only src, UHRS both; a src-less trace must
    # still yield its CDP coordinates
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(0, 0), cdp=(-50000, 150000))])

    result = extract_segy_metadata(path)

    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)


def test_segy_without_coordinates(tmp_path):
    """A SEG-Y file without coordinates yields no bounding box, while its temporal
    extent is still extracted.
    """
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(), _segy_trace()])

    result = extract_segy_metadata(path)

    assert result.bbox_native is None
    assert result.bbox_4326 is None
    assert result.coverage == "full"
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)


def test_segy_mostly_garbage_coordinates_partial(tmp_path):
    """When more than half of the coordinates read from a SEG-Y file are implausible,
    its coverage is reported as partial, and the bounding box is derived from the
    plausible coordinates.
    """
    # implausible coordinate magnitudes are the tell of samples landing
    # mid-trace; above half the samples the coverage is flagged partial, but
    # the plausible traces still contribute
    path = tmp_path / "line.sgy"
    garbage = [_segy_trace(src=(2_000_000_000, 7)) for _ in range(8)]
    good = [
        _segy_trace(src=(-50000, 150000)),
        _segy_trace(src=(-48000, 152000)),
    ]
    _write_segy(path, garbage + good)

    result = extract_segy_metadata(path)

    assert result.coverage == "partial"
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


def test_segy_two_digit_year_temporal_none(tmp_path):
    """A SEG-Y file recording dates with two-digit years yields no temporal extent,
    while its bounding box is still extracted.
    """
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(-50000, 150000), year=24)])

    result = extract_segy_metadata(path)

    assert result.temporal_extent_begin is None
    assert result.temporal_extent_end is None
    assert result.bbox_native is not None


def test_segy_corrupt_time_fields_skipped(tmp_path):
    """Traces of a SEG-Y file with invalid dates or times are left out of the temporal
    extent without interrupting the extraction of the remaining metadata.
    """
    # a single corrupt time field skips only that trace's date and never aborts
    # the extraction (the KMALL guarantee)
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-50000, 150000), hour=99),
            _segy_trace(src=(-48000, 152000), year=2023, day=366),  # not a leap year
            _segy_trace(src=(-49000, 151000), day=272),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.temporal_extent_begin == dt.date(2024, 9, 28)
    assert result.temporal_extent_end == dt.date(2024, 9, 28)
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


def test_segy_trailing_bytes_tolerated(tmp_path):
    """Extra bytes at the end of a SEG-Y file do not affect the trace count, coverage or
    bounding box.
    """
    # a real BSTK file carries a 5,056-byte trailer: floor division ignores it
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [_segy_trace(src=(-50000, 150000)), _segy_trace(src=(-48000, 152000))],
        trailer=b"\x87" * 100,
    )

    result = extract_segy_metadata(path)

    assert result.trace_count == 2
    assert result.coverage == "full"
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


def test_segy_zero_samples_partial_metadata(tmp_path):
    """A SEG-Y file declaring zero samples per trace yields its sample format and
    interval, but no trace count and no bounding box.
    """
    # ns=0 in the binary header leaves no trustworthy trace length; keep the
    # header facts, never fall back to the unreliable per-trace ns field
    path = tmp_path / "line.sgy"
    _write_segy(path, [b"\x00" * 240], ns=0)

    result = extract_segy_metadata(path)

    assert result.samples_per_trace is None
    assert result.trace_count is None
    assert result.sample_format == "ieee-float32"
    assert result.sample_interval == 250
    assert result.bbox_native is None


def test_segy_unknown_format_partial_metadata(tmp_path):
    """A SEG-Y file with an unknown sample format reports the format code, but no trace
    count and no bounding box.
    """
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace()], sample_format=9)

    result = extract_segy_metadata(path)

    assert result.sample_format == "format code 9"
    assert result.trace_count is None
    assert result.bbox_native is None


def test_segy_little_endian(tmp_path):
    """A SEG-Y file written in little-endian byte order is read correctly."""
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [_segy_trace(src=(-50000, 150000), order="<")],
        order="<",
    )

    result = extract_segy_metadata(path)

    assert result.sample_format == "ieee-float32"
    assert result.samples_per_trace == 4
    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)


def test_segy_rev0_extended_count_ignored(tmp_path):
    """In a SEG-Y file of revision 0, the undefined extended header count is ignored, so
    the traces are still read correctly.
    """
    # the rev0 bytes at offset 304 are undefined noise; trusting them would
    # push data_start past the traces
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [_segy_trace(src=(-50000, 150000)), _segy_trace(src=(-48000, 152000))],
        revision=0,
        n_ext=50,
    )

    result = extract_segy_metadata(path)

    assert result.trace_count == 2
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


def test_segy_variable_extended_count_untrusted(tmp_path):
    """A SEG-Y file declaring a variable number of extended headers is still read
    correctly.
    """
    # n_ext == -1 means "variable, stanza-terminated" and is not trusted
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(-50000, 150000))], revision=1, n_ext=-1)

    result = extract_segy_metadata(path)

    assert result.trace_count == 1
    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)


def test_segy_extended_textual_headers(tmp_path):
    """A SEG-Y file with extended textual headers is read correctly, the traces being
    located after those headers.
    """
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [_segy_trace(src=(-50000, 150000)), _segy_trace(src=(-48000, 152000))],
        revision=1,
        n_ext=1,
        extended=b" " * 3200,
    )

    result = extract_segy_metadata(path)

    assert result.trace_count == 2
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


@pytest.mark.parametrize(
    "textual, expected",
    [
        pytest.param(
            "C17 PROJECTION TYPE: PORTUGAL TM06 (EPSG 3763);".encode("cp037"),
            (3763,),
            id="ebcdic",
        ),
        pytest.param(
            b"C 9 crs: etrs89 / portugal tm06, epsg : 3763",
            (3763,),
            id="ascii in lower case",
        ),
        pytest.param(
            (
                "C17 PROJECTION TYPE: TRANSVERSE MERCATOR(EPSG:9807); "
                "C18 VERTICAL DATUM: ZERO HIDROGRAFICO(ZH,EPSG:10349);"
            ).encode("cp037"),
            (9807, 10349),
            id="method and vertical datum",
        ),
        pytest.param(
            "C24 GEODETIC: 3763 : ETRS89 / Portugal TM06 EPSG:258290".encode("cp037"),
            (),
            id="bare number or six digits",
        ),
    ],
)
def test_segy_header_epsg_codes(tmp_path, textual, expected):
    """Every EPSG code written explicitly in the textual header of a SEG-Y file, in
    EBCDIC or ASCII encoding and in any letter case, is reported, while bare numbers and
    codes longer than five digits are not.
    """
    # every explicit code is reported, even those that are no CRS (9807 is a
    # method, 10349 a vertical datum): which one applies is for discovery
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(-50000, 150000))], textual=textual)

    assert extract_segy_metadata(path).header_epsg_codes == expected


def test_segy_sampling_includes_endpoints(tmp_path):
    """When only a sample of the traces of a SEG-Y file is read, the first and last
    traces, which mark the ends of the survey line, are always included in the bounding
    box.
    """
    # 150 single-sample traces: only ~100 are sampled, but the first and last
    # trace (the line endpoints) must always contribute to the bbox
    path = tmp_path / "line.sgy"
    first = _segy_trace(ns=1, bytes_per_sample=1, src=(-52000, 148000))
    middle = [
        _segy_trace(ns=1, bytes_per_sample=1, src=(-49000, 151000)) for _ in range(148)
    ]
    last = _segy_trace(ns=1, bytes_per_sample=1, src=(-45000, 155000))
    _write_segy(path, [first, *middle, last], ns=1, sample_format=8)

    result = extract_segy_metadata(path)

    assert result.trace_count == 150
    assert result.sample_format == "int8"
    assert result.bbox_native == (-52000.0, 148000.0, -45000.0, 155000.0)


@pytest.mark.parametrize(
    "content",
    [b"", b"tiny", b"\x00" * 4000, b"\xff" * 4000],
)
def test_segy_not_a_segy_raises(tmp_path, content):
    """Files too small to hold a SEG-Y trace, or whose header holds an invalid sample
    format, are rejected as not being SEG-Y files.
    """
    # too small to hold a trace, or a binary header whose format code is
    # invalid in both byte orders
    path = tmp_path / "junk.sgy"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        extract_segy_metadata(path)


# production holds 925 .SEGY files besides the 68k lowercase ones, so the
# uppercase variants are pinned here too
@pytest.mark.parametrize("suffix", [".sgy", ".segy", ".SGY", ".SEGY"])
def test_dispatch_routes_segy(tmp_path, suffix):
    """SEG-Y files are recognised by their extension in either lower or upper case, and
    their metadata, including their file size, is extracted.
    """
    path = tmp_path / f"line{suffix}"
    _write_segy(path, [_segy_trace(src=(-50000, 150000))])

    result = dispatch.dispatch_extractor(path)

    assert isinstance(result, schemas.SegyMetadata)
    assert result.file_size_bytes == path.stat().st_size


def test_segy_implausible_span_discards_bbox(tmp_path):
    """When the coordinates of a SEG-Y file span an implausibly large area, its bounding
    box and track are discarded and its coverage is reported as partial, while its other
    metadata is kept.
    """
    # real owf-2025 files exist whose src AND cdp fields hold noise around the
    # projection origin with sporadic spikes into the millions; the resulting
    # box spanned thousands of km while coverage still said "full". Rejecting
    # the outliers instead would leave a small credible box AT the origin,
    # which is on land in central Portugal, so the whole box goes.
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(140, 120), scalco=-100),
            _segy_trace(src=(-240, -330), scalco=-100),
            _segy_trace(src=(588515700, 600505400), scalco=-100),
            _segy_trace(src=(-100, -80), scalco=-100),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_native is None
    assert result.bbox_4326 is None
    # no track either: it would draw the same noise
    assert result.sampled_positions == ()
    assert result.coverage == "partial"
    # the rest of the metadata is unaffected and still worth having
    assert result.trace_count == 4
    assert result.sample_format == "ieee-float32"
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)


def test_segy_implausible_span_without_any_rejected_value(tmp_path):
    """A SEG-Y file whose individual coordinates are each plausible, but which together
    span an implausibly large area, gets no bounding box and a partial coverage.
    """
    # the case a garbage-count rule cannot catch: every value stays inside the
    # per-value plausibility filter, so only the span betrays the noise
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(140, 120), scalco=-100),
            _segy_trace(src=(-986000000, -493000000), scalco=-100),
            _segy_trace(src=(995000000, 497000000), scalco=-100),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_native is None
    assert result.coverage == "partial"


def test_segy_geographic_implausible_span_discards_bbox(tmp_path):
    """When the coordinates in degrees of a SEG-Y file span an implausibly large area,
    no bounding box and no coordinate reference system are reported, and its coverage is
    reported as partial.
    """
    # the same protection on the only path that draws a map rectangle
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-87500, 422300), scalco=-10000, units=3),
            _segy_trace(src=(1200000, -600000), scalco=-10000, units=3),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_4326 is None
    assert result.bbox_native is None
    assert result.epsg is None  # no CRS claim without a box to attach it to
    assert result.coverage == "partial"


def test_segy_survey_wide_span_is_kept(tmp_path):
    """A legitimately long SEG-Y survey line of about 60 kilometres keeps its bounding
    box and full coverage.
    """
    # a legitimately long line must survive: real files measure up to 61.5 km
    # and the cap is 200 km, so a 60 km line is still stored
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-13000000, 2200000), scalco=-100),
            _segy_trace(src=(-13000000, 8200000), scalco=-100),
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_native == (-130000.0, 22000.0, -130000.0, 82000.0)
    assert result.coverage == "full"


def test_segy_burst_corruption_span_discards_bbox(tmp_path):
    """A SEG-Y file in which a few corrupt traces stretch the bounding box to hundreds
    of kilometres gets no bounding box and a partial coverage, while its trace count is
    kept.
    """
    # the second junk mode the 66k scan found (A7808 ET_SBP): a real ~2.5 km
    # line with a burst of corrupt-nav traces stretched the box to ~494 km with
    # garbage_count 0, which the old 500 km cap let through as coverage=full.
    # The 200 km cap catches it while leaving every real line (<= 61.5 km) alone.
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-12198249, 5017758), scalco=-100),  # (-121982, 50177)
            _segy_trace(src=(-738249, -44428591), scalco=-100),  # (-7382, -444285)
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_native is None
    assert result.coverage == "partial"
    # the header facts are unaffected and still worth keeping
    assert result.trace_count == 2


def test_segy_low_support_bbox_dropped(tmp_path):
    """When only a small fraction of the sampled traces of a SEG-Y file carry
    coordinates, its bounding box and track are discarded and its coverage is reported
    as partial.
    """
    # the third junk mode the scan found (A7808 GEOM): a 95-182 GB file where
    # only 2-3 of 100 sampled traces carry a fix and the rest are coordinate-less.
    # A box from 3 points covers a sliver of the real line while claiming full
    # coverage, so it is dropped and the coverage flagged.
    path = tmp_path / "line.sgy"
    traces = [_segy_trace(src=(-50000, 150000))] * 3 + [_segy_trace()] * 97
    _write_segy(path, traces)

    result = extract_segy_metadata(path)

    assert result.trace_count == 100
    assert result.bbox_native is None
    assert result.sampled_positions == ()
    assert result.coverage == "partial"


def test_segy_low_support_kept_for_small_file(tmp_path):
    """A SEG-Y file with only a few traces keeps its bounding box and full coverage even
    when only some of its traces carry coordinates.
    """
    # the guard: a genuinely small file with only a few traces keeps its box even
    # when only some carry a fix - too few samples to trust the support ratio
    path = tmp_path / "line.sgy"
    traces = [
        _segy_trace(src=(-50000, 150000)),
        _segy_trace(src=(-48000, 152000)),
    ] + [_segy_trace()] * 6
    _write_segy(path, traces)

    result = extract_segy_metadata(path)

    assert result.trace_count == 8
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)
    assert result.coverage == "full"


def test_segy_units_unset_treated_as_metres(tmp_path):
    """A SEG-Y file that does not specify its coordinate units is read as having
    coordinates in metres, yielding a native bounding box without any coordinate
    reference system.
    """
    # the real raw-file case: the UHRS rev1.segy files leave units at 0
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(-50000, 150000), units=0)])

    result = extract_segy_metadata(path)

    assert result.coordinate_units == "unset"
    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)
    assert result.bbox_4326 is None
    assert result.epsg is None


def test_segy_geographic_out_of_range_rejected(tmp_path):
    """In a SEG-Y file with coordinates in degrees, values outside the valid range of
    longitude and latitude are excluded from the bounding box.
    """
    # the plausibility filter guards the only path that draws a map rectangle:
    # a trace claiming degrees but carrying projected metres must not become a
    # bbox somewhere off the planet
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [
            _segy_trace(src=(-87500, 422300), scalco=-10000, units=3),
            _segy_trace(src=(-500000, 1500000), units=3),  # metres in a degrees file
        ],
    )

    result = extract_segy_metadata(path)

    assert result.bbox_4326 == (-8.75, 42.23, -8.75, 42.23)
    assert result.coverage == "full"  # one garbage trace out of two is not "> half"


def test_segy_coverage_boundary_at_exactly_half(tmp_path):
    """A SEG-Y file in which exactly half of the coordinates are implausible keeps a
    full coverage, while one with more than half is reported as partial.
    """
    # exactly half the samples garbage stays "full"; one more tips it to partial
    path = tmp_path / "line.sgy"
    good = [_segy_trace(src=(-50000, 150000)), _segy_trace(src=(-48000, 152000))]
    garbage = [_segy_trace(src=(2_000_000_000, 7)) for _ in range(2)]
    _write_segy(path, good + garbage)
    assert extract_segy_metadata(path).coverage == "full"

    _write_segy(path, good + garbage + [_segy_trace(src=(2_000_000_000, 7))])
    assert extract_segy_metadata(path).coverage == "partial"


def test_segy_extended_headers_not_fitting_are_ignored(tmp_path):
    """A SEG-Y file declaring more extended headers than it can hold has that
    declaration ignored, so its traces are still read correctly.
    """
    # a declared extended-header count that would leave no room for a trace is
    # garbage; trusting it would push data_start past the end of the file and
    # yield a negative trace_count
    path = tmp_path / "line.sgy"
    _write_segy(
        path,
        [_segy_trace(src=(-50000, 150000))],
        revision=1,
        n_ext=99,  # 99 * 3200 bytes that are not in the file
    )

    result = extract_segy_metadata(path)

    assert result.trace_count == 1
    assert result.bbox_native == (-50000.0, 150000.0, -50000.0, 150000.0)


def test_segy_little_endian_revision_word(tmp_path):
    """The revision number of a little-endian SEG-Y file is read correctly, so its
    extended header is accounted for and its traces are read correctly.
    """
    # a little-endian writer storing the rev1-style uint16 0x0100 puts the major
    # number in the SECOND byte; reading a single byte would see revision 0 and
    # then ignore the extended header, shifting the whole trace grid
    path = tmp_path / "line.sgy"
    header = bytearray(_segy_binary_header(4, 5, 250, 1, 1, "<"))
    header[300:302] = b"\x00\x01"
    path.write_bytes(
        b" " * 3200
        + bytes(header)
        + b" " * 3200
        + _segy_trace(src=(-50000, 150000), order="<")
        + _segy_trace(src=(-48000, 152000), order="<")
    )

    result = extract_segy_metadata(path)

    assert result.trace_count == 2
    assert result.bbox_native == (-50000.0, 150000.0, -48000.0, 152000.0)


def test_segy_rev2_extra_trace_headers_partial_metadata(tmp_path):
    """A SEG-Y revision 2 file whose traces carry additional headers yields its sample
    format, but no trace count and no bounding box, rather than incorrect ones.
    """
    # rev2 lets each trace carry additional 240-byte headers; the trace length
    # is then unknown to us, and a desynced grid would store a confidently
    # wrong bbox, so only the header facts survive
    path = tmp_path / "line.sgy"
    header = bytearray(_segy_binary_header(4, 5, 250, 2, 0, ">"))
    struct.pack_into(">i", header, 306, 1)
    path.write_bytes(
        b" " * 3200
        + bytes(header)
        + b"".join(
            _segy_trace(src=src) + b"\x00" * 240
            for src in ((-50000, 150000), (-48000, 152000))
        )
    )

    result = extract_segy_metadata(path)

    assert result.sample_format == "ieee-float32"
    assert result.trace_count is None
    assert result.bbox_native is None


def test_segy_truncated_binary_header_raises(tmp_path):
    """A SEG-Y file that ends within its binary header is rejected."""
    # a file that ends inside the binary header must still raise ValueError
    # rather than let a struct error escape
    path = tmp_path / "line.sgy"
    _write_segy(path, [_segy_trace(src=(-50000, 150000))])
    truncated = tmp_path / "truncated.sgy"
    truncated.write_bytes(path.read_bytes()[:3400])

    with pytest.raises(ValueError):
        extract_segy_metadata(truncated)


def test_segy_trace_count_zero(tmp_path):
    """A SEG-Y file holding its headers but no complete trace reports zero traces, its
    samples per trace, and no bounding box or temporal extent.
    """
    # a file holding the headers but less than one full trace
    path = tmp_path / "line.sgy"
    path.write_bytes(
        b" " * 3200 + _segy_binary_header(1000, 5, 250, 1, 0, ">") + b"\x00" * 300
    )

    result = extract_segy_metadata(path)

    assert result.trace_count == 0
    assert result.samples_per_trace == 1000
    assert result.bbox_native is None
    assert result.temporal_extent_begin is None


# Teledyne PDS builders: a few binary bytes, then text sections ending at a blank
# line, with an invented run line, vessel and survey area
_PDS_BINARY_TAG = b"\xfe\x03\x00\x9a\x07\x00"
_PDS_UTM_29N = (
    b"[CoordSystem Backup]\n"
    b"CoordSystem = WGS 84 - UTM Zone 29N\n"
    b"Projection medthod = Universal Transverse Mercator\n"
    b"Ellipsoid name = WGS84\n"
    b"\n"
    b"[GEODESY_PROJECTION_BACKUP]\n"
    b"LatOrigin = 0\n"
    b"LonOrigin = -9\n"
    b"FalseEast = 500000\n"
    b"FalseNorth = 0\n"
)
_PDS_PATTERN_WITH_POINTS = (
    b"Type = 11\n"
    b"Point(0) = 1,510000.000000,4200000.000000,0.000000,0,,0.000000,0.000000\n"
    b"Point(1) = 1,510000.000000,4210000.000000,0.000000,0,,0.000000,10.000000\n"
    b"ParBoxWidthR = 200\n"
    b"ParBoxWidthL = 500\n"
)


def _write_pds(
    path,
    coordinate_system=_PDS_UTM_29N,
    pattern=_PDS_PATTERN_WITH_POINTS,
    line_end=b"\n",
):
    header = (
        b"[HEADER]\n"
        b"PdsVersion = 4,1,2,10\n"
        b"VesselName = RV Example\n"
        b"RunlineName = Box(2).C.L\n"
        b"AcquisLogStartTime = 20200315-101500\n"
    )
    # PDS 4.1 glues a binary tag and the run line name before its pattern section
    run_line_pattern = _PDS_BINARY_TAG + b"Box(2).C.L\x00[Box(2)]\n" + pattern
    # a pattern of the project that the run line does not follow
    other_pattern = (
        b"[Other_Box]\n"
        b"Type = 11\n"
        b"Point(0) = 1,600000.000000,4100000.000000,0.000000,0,,0.000000,0.000000\n"
        b"ParBoxWidthR = 100\n"
        b"ParBoxWidthL = 100\n"
    )
    sections = [header, coordinate_system, run_line_pattern, other_pattern]
    text = b"\n".join(sections) + b"\n"
    path.write_bytes(bytes(17) + text.replace(b"\n", line_end) + _PDS_BINARY_TAG)


@pytest.mark.parametrize(
    "line_end",
    [pytest.param(b"\n", id="lf"), pytest.param(b"\r\n", id="crlf, as in pds 3.9")],
)
def test_pds_metadata_fields(tmp_path, line_end):
    """A Teledyne PDS file is recognised and the metadata in its text header is read.
    Its temporal extent is the day on which the acquisition started.
    Its coordinate reference system is the WGS 84 / UTM zone described in the header.
    Its bounding box is the planned area of its own run line, among the lines it lists.
    This holds for the line endings of both older and newer versions of the software.
    """
    path = tmp_path / "line.pds"
    _write_pds(path, line_end=line_end)

    result = dispatch.dispatch_extractor(path)

    assert result.driver == "Teledyne PDS"
    assert result.file_size_bytes == path.stat().st_size
    assert result.temporal_extent_begin == dt.date(2020, 3, 15)
    assert result.temporal_extent_end == dt.date(2020, 3, 15)
    assert result.epsg == 32629
    # the planned line, widened on both sides by the wider side of its box
    assert result.bbox_native == (509500.0, 4200000.0, 510500.0, 4210000.0)
    lon_min, lat_min, lon_max, lat_max = result.bbox_4326
    assert -8.9 < lon_min < lon_max < -8.8
    assert 37.9 < lat_min < lat_max < 38.1


def test_pds_without_points(tmp_path):
    """A Teledyne PDS file whose planned line holds no points has no bounding box.
    Its temporal extent and its coordinate reference system are still extracted.
    """
    path = tmp_path / "line.pds"
    _write_pds(path, pattern=b"Type = 9\n")

    result = extract_pds_metadata(path)

    assert result.temporal_extent_begin == dt.date(2020, 3, 15)
    assert result.epsg == 32629
    assert result.bbox_native is None
    assert result.bbox_4326 is None


def test_pds_in_another_crs(tmp_path):
    """A Teledyne PDS file not in WGS 84 / UTM gets no coordinate reference system.
    It gets no bounding box either, as the survey mission's system is never used for it.
    Its temporal extent is still extracted.
    """
    path = tmp_path / "line.pds"
    _write_pds(
        path,
        coordinate_system=(
            b"[CoordSystem Backup]\n"
            b"CoordSystem = ETRS 89 - Portugal TM06\n"
            b"Projection medthod = Transverse Mercator\n"
            b"Ellipsoid name = GRS80\n"
            b"\n"
            b"[GEODESY_PROJECTION_BACKUP]\n"
            b"LatOrigin = 39.668258\n"
            b"LonOrigin = -8.133108\n"
            b"FalseEast = 0\n"
            b"FalseNorth = 0\n"
        ),
    )

    result = extract_pds_metadata(path)

    assert result.temporal_extent_begin == dt.date(2020, 3, 15)
    assert result.epsg is None
    assert result.crs_name is None
    assert result.bbox_4326 is None
    # a native bbox without a CRS would be placed with the survey mission's CRS
    assert result.bbox_native is None


def test_pds_not_a_pds_raises(tmp_path):
    """A file that does not start with the header of a Teledyne PDS file is rejected."""
    path = tmp_path / "junk.pds"
    path.write_bytes(b"this is not a pds file")
    with pytest.raises(ValueError):
        extract_pds_metadata(path)
