import logging
from pathlib import Path

from .gdal_raster import derive_raster_preview
from .gdal_vector import derive_vector_preview
from .kmall import derive_kmall_preview
from .schemas import DerivedPreview
from .segy import derive_segy_preview

logger = logging.getLogger(__name__)

# Rasters, vectors and the vessel tracks of KMALL and SEG-Y files. XYZ grids
# cannot declare a CRS and ASC/FLT grids only do so with a .prj sidecar, so
# rasters may fall back to the survey mission's implicit CRS.
# SEG-Y tracks take the CRS discovery placed the record's bbox with instead
_RASTER_EXTENSIONS = frozenset({".tif", ".tiff", ".xyz", ".asc", ".flt"})
_VECTOR_EXTENSIONS = frozenset({".shp", ".gpkg", ".geojson"})
_KMALL_EXTENSIONS = frozenset({".kmall"})
_SEGY_EXTENSIONS = frozenset({".sgy", ".segy"})


def can_derive(path: Path | str) -> bool:
    p = Path(path)
    suffix = p.suffix.lower()
    # Because directories such as "F3_2022.tif" exist in the archive
    return (
        suffix in _RASTER_EXTENSIONS
        or suffix in _VECTOR_EXTENSIONS
        or suffix in _KMALL_EXTENSIONS
        or suffix in _SEGY_EXTENSIONS
    ) and p.is_file()


def dispatch_deriver(
    path: Path | str, implicit_epsg_code: int, discovered_epsg_code: int | None
) -> DerivedPreview | None:
    """Route a file to its preview deriver by extension.

    sync and slow: the whole file is read to build the overview
    Async callers must run this in a worker thread
    The implicit EPSG code is the survey mission's, only rasters without a CRS
    of their own use it. The discovered EPSG code is the one in the record's
    discovery info, only SEG-Y files use it.
    Returns None for unsupported extensions and directories.
    """
    p = Path(path)
    if not can_derive(p):
        return None
    if p.suffix.lower() in _VECTOR_EXTENSIONS:
        return derive_vector_preview(p)
    if p.suffix.lower() in _KMALL_EXTENSIONS:
        return derive_kmall_preview(p)
    if p.suffix.lower() in _SEGY_EXTENSIONS:
        return derive_segy_preview(p, discovered_epsg_code)
    return derive_raster_preview(p, implicit_epsg_code)
