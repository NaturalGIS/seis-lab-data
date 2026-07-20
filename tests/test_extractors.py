"""Unit tests for the metadata extractors package.

Pure functions, no DB: these run by default (no marker). GDAL is required; the
module self-skips where it is unavailable. Everything is exercised against
synthetic files built in-test, so the suite needs no sample-data archive.
"""

import datetime as dt
import logging
import math
import struct

import pytest

pytest.importorskip("osgeo")

from osgeo import gdal, ogr, osr  # noqa: E402

from seis_lab_data.tasks.extractors import (  # noqa: E402
    dispatch,
    schemas,
)
from seis_lab_data.tasks.extractors.gdal_raster import (  # noqa: E402
    extract_raster_metadata,
)
from seis_lab_data.tasks.extractors.gdal_vector import (  # noqa: E402
    extract_vector_metadata,
)
from seis_lab_data.tasks.extractors.kmall import (  # noqa: E402
    extract_kmall_metadata,
)

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
    path = tmp_path_factory.mktemp("vector") / "points.shp"
    _write_shapefile(path, _srs(_PT_TM06))
    return path


@pytest.fixture(scope="session")
def synthetic_shapefile_no_prj(tmp_path_factory):
    path = tmp_path_factory.mktemp("vector_noprj") / "points.shp"
    _write_shapefile(path, None)
    return path


@pytest.fixture(scope="session")
def broken_vector(tmp_path_factory):
    # A valid shapefile with its .shx removed: reproduces the real prr_eolicas
    # "missing .shx" condition, which GDAL refuses to open (SHAPE_RESTORE_SHX
    # defaults to NO) -> RuntimeError.
    path = tmp_path_factory.mktemp("broken") / "points.shp"
    _write_shapefile(path, _srs(_PT_TM06))
    path.with_suffix(".shx").unlink()
    return path


def test_raster_metadata_fields(synthetic_geotiff):
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
    result = extract_raster_metadata(synthetic_xyz)

    assert result.driver == "XYZ"
    assert result.width == 3
    assert result.height == 3
    # No .prj alongside an XYZ grid: no CRS, native bbox only.
    assert result.epsg is None
    assert result.bbox_native is not None
    assert result.bbox_4326 is None


def test_vector_metadata_fields(synthetic_shapefile):
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
    result = extract_vector_metadata(synthetic_shapefile_no_prj)

    assert result.epsg is None
    assert result.crs_name is None
    assert result.crs_wkt is None
    assert result.bbox_4326 is None
    assert result.bbox_native is not None
    assert result.feature_count == 3


def test_broken_vector_raises(broken_vector):
    with pytest.raises(RuntimeError):
        extract_vector_metadata(broken_vector)


def test_dispatch_routes_raster(synthetic_geotiff):
    assert isinstance(
        dispatch.dispatch_extractor(synthetic_geotiff), schemas.RasterMetadata
    )


def test_dispatch_routes_xyz(synthetic_xyz):
    result = dispatch.dispatch_extractor(synthetic_xyz)
    assert isinstance(result, schemas.RasterMetadata)
    assert result.driver == "XYZ"


def test_dispatch_routes_vector(synthetic_shapefile):
    assert isinstance(
        dispatch.dispatch_extractor(synthetic_shapefile), schemas.VectorMetadata
    )


@pytest.mark.parametrize("suffix", [".shx", ".dbf", ".prj", ".cpg", ".qmd", ".sbn"])
def test_dispatch_ignores_sidecars(tmp_path, suffix):
    sidecar = tmp_path / f"points{suffix}"
    sidecar.write_bytes(b"\x00")
    assert dispatch.dispatch_extractor(sidecar) is None


@pytest.mark.parametrize("suffix", [".sgy", ".segy"])
def test_dispatch_stubs_return_none(tmp_path, suffix):
    stub = tmp_path / f"survey{suffix}"
    stub.write_bytes(b"\x00")
    assert dispatch.dispatch_extractor(stub) is None


def test_dispatch_unknown_extension(tmp_path):
    unknown = tmp_path / "notes.txt"
    unknown.write_text("hello")
    assert dispatch.dispatch_extractor(unknown) is None


def test_dispatch_directory_named_like_raster(tmp_path):
    # A real directory named "F3_2022.tif" exists in the archive; it must not be opened.
    fake = tmp_path / "F3_2022.tif"
    fake.mkdir()
    assert dispatch.dispatch_extractor(fake) is None


def test_dispatch_big_file_logs(synthetic_geotiff, monkeypatch, caplog):
    monkeypatch.setattr(dispatch, "_BIG_FILE_LOG_BYTES", 0)
    with caplog.at_level(logging.INFO, logger=dispatch.logger.name):
        result = dispatch.dispatch_extractor(synthetic_geotiff)
    assert isinstance(result, schemas.RasterMetadata)
    assert any("large raster" in record.message for record in caplog.records)


def test_raster_describe(synthetic_geotiff):
    text = extract_raster_metadata(synthetic_geotiff).describe()
    assert text.startswith("Auto-extracted: GTiff raster")
    assert "TM06" in text
    assert "EPSG:3763" in text
    assert len(text) <= 500


def test_vector_describe(synthetic_shapefile):
    text = extract_vector_metadata(synthetic_shapefile).describe()
    assert text.startswith("Auto-extracted: ESRI Shapefile vector")
    assert "Point" in text
    assert len(text) <= 500


def test_describe_truncates_to_500():
    absurd = schemas.RasterMetadata(
        driver="GTiff",
        width=1,
        height=1,
        band_count=1,
        crs_name="X" * 2000,
    )
    assert len(absurd.describe()) == 500


def test_describe_crs_unknown():
    text = schemas.VectorMetadata(
        driver="ESRI Shapefile",
        layer_count=1,
        feature_count=0,
        geometry_type="Point",
    ).describe()
    assert "CRS: unknown." in text


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
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1), (40.6, -9.2)])

    result = extract_kmall_metadata(path)

    assert isinstance(result, schemas.KmallMetadata)
    assert result.driver == "KMALL"
    assert result.echo_sounder_id == 712
    assert result.datagram_count == 5
    assert result.position_count == 3
    assert result.epsg == 4326
    assert result.bbox_4326 == (-9.3, 40.5, -9.1, 40.7)
    assert result.bbox_native == result.bbox_4326
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def test_kmall_cpo_fallback(tmp_path):
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1)], dgm_type=b"#CPO")

    result = extract_kmall_metadata(path)

    assert result.position_count == 2
    assert result.bbox_4326 == (-9.3, 40.5, -9.1, 40.7)


def test_kmall_spo_takes_precedence_over_cpo(tmp_path):
    # SPO is the primary source; a divergent CPO feed must be IGNORED, never
    # merged into the bbox or the fix count
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3), (40.7, -9.1)], cpo_fixes=[(50.0, 5.0)])

    result = extract_kmall_metadata(path)

    assert result.position_count == 2
    assert result.bbox_4326 == (-9.3, 40.5, -9.1, 40.7)


def test_kmall_short_position_body_skipped(tmp_path):
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

    assert result.position_count == 1
    assert result.bbox_4326 == (-9.2, 40.6, -9.2, 40.6)


def test_kmall_without_positions(tmp_path):
    path = tmp_path / "line.kmall"
    _write_kmall(path, [])

    result = extract_kmall_metadata(path)

    assert result.bbox_4326 is None
    assert result.epsg is None
    assert result.position_count == 0
    assert result.temporal_extent_begin == dt.date(2024, 9, 28)
    assert result.temporal_extent_end == dt.date(2024, 9, 29)


def test_kmall_skips_garbage_fixes(tmp_path):
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

    assert result.position_count == 1
    assert result.bbox_4326 == (-9.2, 40.6, -9.2, 40.6)


def test_kmall_truncated_tail_garbage(tmp_path):
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    with path.open("ab") as fh:
        fh.write(b"X" * 40)  # parses as an invalid header -> walk stops

    result = extract_kmall_metadata(path)

    assert result.datagram_count == 3
    assert result.position_count == 1


def test_kmall_truncated_tail_beyond_eof(tmp_path):
    # the realistic acquisition-crash shape: a well-formed header whose
    # num_bytes claims data beyond the end of the file
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    with path.open("ab") as fh:
        fh.write(_KMALL_HEADER.pack(99999, b"#MRZ", 0, 0, 712, _KMALL_T0 + 2, 0))

    result = extract_kmall_metadata(path)

    assert result.datagram_count == 3
    assert result.position_count == 1


def test_kmall_garbage_raises(tmp_path):
    path = tmp_path / "junk.kmall"
    path.write_bytes(b"this is definitely not a kmall file")
    with pytest.raises(ValueError):
        extract_kmall_metadata(path)


@pytest.mark.parametrize("content", [b"", b"tiny"])
def test_kmall_too_small_raises(tmp_path, content):
    # empty or sub-header files never enter the walk and must still raise
    path = tmp_path / "empty.kmall"
    path.write_bytes(content)
    with pytest.raises(ValueError):
        extract_kmall_metadata(path)


def test_dispatch_routes_kmall(tmp_path):
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    assert isinstance(dispatch.dispatch_extractor(path), schemas.KmallMetadata)


def test_dispatch_big_kmall_logs(tmp_path, monkeypatch, caplog):
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    monkeypatch.setattr(dispatch, "_BIG_FILE_LOG_BYTES", 0)
    with caplog.at_level(logging.INFO, logger=dispatch.logger.name):
        result = dispatch.dispatch_extractor(path)
    assert isinstance(result, schemas.KmallMetadata)
    assert any("large KMALL file" in record.message for record in caplog.records)


def test_kmall_describe(tmp_path):
    path = tmp_path / "line.kmall"
    _write_kmall(path, [(40.5, -9.3)])
    text = extract_kmall_metadata(path).describe()
    assert text.startswith("Auto-extracted: Kongsberg KMALL, EM 712")
    assert "position fix(es)" in text
    assert "EPSG:4326" in text
    assert len(text) <= 500
