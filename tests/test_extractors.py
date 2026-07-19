"""Unit tests for the metadata extractors package.

Pure functions, no DB: these run by default (no marker). GDAL is required; the
module self-skips where it is unavailable. Everything is exercised against
synthetic files built in-test, so the suite needs no sample-data archive.
"""

import logging

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


@pytest.mark.parametrize("suffix", [".kmall", ".sgy", ".segy"])
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
