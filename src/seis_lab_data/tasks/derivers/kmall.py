import json
import logging
import uuid
from pathlib import Path

from osgeo import gdal

from ..extractors.kmall import collect_position_fixes
from .gdal_vector import derive_vector_preview
from .schemas import DerivedPreview

logger = logging.getLogger(__name__)

gdal.UseExceptions()


def derive_kmall_preview(path: Path | str) -> DerivedPreview:
    """Render the vessel track of a KMALL file as a small transparent WEBP image.

    The track is drawn from the same position fixes as the extracted bbox, one
    point per fix, already in geographic degrees.

    Pure sync and potentially slow (every datagram header of the file is read),
    so async callers must run this in a worker thread (e.g.
    anyio.to_thread.run_sync).
    """
    fixes = collect_position_fixes(path)
    if not fixes:
        raise ValueError(f"KMALL {path} has no position fixes to render")
    track = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "MultiPoint", "coordinates": fixes},
            }
        ],
    }
    # rendered through the vector deriver, so tracks look like the other vector
    # previews; the unique name survives concurrent renders in one worker
    vsi_path = f"/vsimem/{uuid.uuid4().hex}.geojson"
    gdal.FileFromMemBuffer(vsi_path, json.dumps(track))
    try:
        return derive_vector_preview(vsi_path)
    finally:
        gdal.Unlink(vsi_path)
