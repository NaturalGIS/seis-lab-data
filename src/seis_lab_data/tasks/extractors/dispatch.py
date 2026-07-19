import logging
from pathlib import Path

from .gdal_raster import extract_raster_metadata
from .gdal_vector import extract_vector_metadata
from .schemas import ExtractionResult

logger = logging.getLogger(__name__)

_RASTER_EXTENSIONS = frozenset(
    {".tif", ".tiff", ".asc", ".flt", ".grd", ".xyz", ".nc", ".nc4"}
)
# .nc/.nc4 are kept for gridded NetCDF (served by the plain GDAL raster path); the
# ubuntu-small image has no netCDF driver yet, so extraction fails best-effort until the
# base image moves to gdal:ubuntu-full. Production has 0 .nc files today.

# Sidecars (.shx/.dbf/.prj/.cpg/.qmd/.sbn/.sbx ...) are deliberately absent so they never
# trigger extraction; GDAL reads them implicitly when opening the primary file. .kmz is
# excluded (needs LIBKML, absent from the image); .gdb (a directory) and S-57 .000 too.
_VECTOR_EXTENSIONS = frozenset({".shp", ".gpkg", ".geojson", ".kml", ".dxf"})

# Dedicated KMALL/SEG-Y extractors land in later blueprints; stubbed to None for now.
_STUB_EXTENSIONS = frozenset({".kmall", ".sgy", ".segy"})

_BIG_FILE_LOG_BYTES = 1024**3  # log-only threshold; no hard size limit


def dispatch_extractor(path: Path | str) -> ExtractionResult | None:
    """Route a file to its metadata extractor by extension.

    Pure sync and potentially slow: GDAL's XYZ driver scans the whole file on open,
    so a multi-GB grid can take ~1 minute. Async callers must run this in a worker
    thread (e.g. anyio.to_thread.run_sync). Returns None for unsupported extensions,
    directories, and the KMALL/SEG-Y stubs.
    """
    p = Path(path)
    if not p.is_file():
        # A real directory named "F3_2022.tif" exists in the archive.
        return None
    suffix = p.suffix.lower()
    if suffix in _RASTER_EXTENSIONS:
        size = p.stat().st_size
        if size > _BIG_FILE_LOG_BYTES:
            logger.info("Extracting metadata from large raster %s (%d bytes)", p, size)
        return extract_raster_metadata(p)
    if suffix in _VECTOR_EXTENSIONS:
        return extract_vector_metadata(p)
    if suffix in _STUB_EXTENSIONS:
        return None
    return None
