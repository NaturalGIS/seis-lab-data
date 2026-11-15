import json
import logging
import uuid
from pathlib import Path

from osgeo import (
    gdal,
    osr,
)

from ..extractors.common import project_bbox_to_wgs84
from ..extractors.segy import extract_segy_metadata
from .gdal_vector import derive_vector_preview
from .schemas import DerivedPreview

logger = logging.getLogger(__name__)

gdal.UseExceptions()


def derive_segy_preview(path: Path | str, epsg_code: int | None) -> DerivedPreview:
    """Render the track of a SEG-Y line as a small transparent WEBP image.

    The track joins, in trace order, the trace positions the extractor samples for
    the bbox, so the track and the record's bbox come from the same points.
    `epsg_code` is the CRS discovery applied to that bbox. A file without one, or
    with fewer than two distinct positions, raises ValueError, so its card keeps
    the sample image.

    Pure sync, reading the same ~100 trace headers as discovery, so async callers
    must run this in a worker thread (e.g. anyio.to_thread.run_sync).
    """
    if epsg_code is None:
        raise ValueError(f"SEG-Y {path} has no CRS to place its track with")
    metadata = extract_segy_metadata(path)
    positions = metadata.sampled_positions
    if len(set(positions)) < 2:
        raise ValueError(f"SEG-Y {path} has no track to render")
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    coordinates = _transform_positions_to_wgs84(positions, srs)
    # a line, as lone points lose their colour to WEBP's lossy chroma
    geometry = {"type": "LineString", "coordinates": coordinates}
    track = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": geometry}],
    }
    # the map pins the image to the record's bbox, projected from the 4 box corners
    record_bbox_4326 = project_bbox_to_wgs84(metadata.bbox_native, srs)
    # the unique name survives concurrent renders in one worker
    vsi_path = f"/vsimem/{uuid.uuid4().hex}.geojson"
    gdal.FileFromMemBuffer(vsi_path, json.dumps(track))
    try:
        return derive_vector_preview(vsi_path, record_bbox_4326)
    finally:
        gdal.Unlink(vsi_path)


def _transform_positions_to_wgs84(
    positions: tuple[tuple[float, float], ...], source_srs: osr.SpatialReference
) -> list[list[float]]:
    source = source_srs.Clone()
    wgs84 = osr.SpatialReference()
    wgs84.ImportFromEPSG(4326)
    # (x, y) is (lon, lat) when geographic, but EPSG:4326 orders (lat, lon)
    for srs in (source, wgs84):
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, wgs84)
    return [[lon, lat] for lon, lat, _ in transform.TransformPoints(positions)]
