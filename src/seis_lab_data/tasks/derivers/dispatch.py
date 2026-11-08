import logging
from pathlib import Path

from .gdal_raster import derive_raster_preview
from .gdal_vector import derive_vector_preview
from .kmall import derive_kmall_preview
from .schemas import DerivedPreview

logger = logging.getLogger(__name__)

# Rasters, vectors and KMALL vessel tracks. XYZ grids cannot declare a CRS and
# ASC/FLT grids only do so with a .prj sidecar, so rasters may fall back to the
# survey mission's implicit CRS. SEG-Y has no deriver: its record cards show a
# static sample image instead
_RASTER_EXTENSIONS = frozenset({".tif", ".tiff", ".xyz", ".asc", ".flt"})
_VECTOR_EXTENSIONS = frozenset({".shp", ".gpkg", ".geojson"})
_KMALL_EXTENSIONS = frozenset({".kmall"})


def can_derive(path: Path | str) -> bool:
    p = Path(path)
    suffix = p.suffix.lower()
    # Because directories such as "F3_2022.tif" exist in the archive
    return (
        suffix in _RASTER_EXTENSIONS
        or suffix in _VECTOR_EXTENSIONS
        or suffix in _KMALL_EXTENSIONS
    ) and p.is_file()


def dispatch_deriver(
    path: Path | str, implicit_epsg_code: int
) -> DerivedPreview | None:
    """Route a file to its preview deriver by extension.

    sync and slow: the whole file is read to build the overview
    Async callers must run this in a worker thread
    The implicit EPSG code is the survey mission's, only rasters without a CRS
    of their own use it.
    Returns None for unsupported extensions and directories.
    """
    p = Path(path)
    if not can_derive(p):
        return None
    if p.suffix.lower() in _VECTOR_EXTENSIONS:
        return derive_vector_preview(p)
    if p.suffix.lower() in _KMALL_EXTENSIONS:
        return derive_kmall_preview(p)
    return derive_raster_preview(p, implicit_epsg_code)
