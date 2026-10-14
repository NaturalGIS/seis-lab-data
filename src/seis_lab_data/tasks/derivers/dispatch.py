import logging
from pathlib import (
    Path,
    PurePath,
)

from .gdal_raster import derive_raster_preview
from .gdal_vector import derive_vector_preview
from .kmall import derive_kmall_preview
from .schemas import DerivedPreview

logger = logging.getLogger(__name__)

# Rasters and vectors which carry their own CRS, plus KMALL vessel tracks.
# The remaining formats are tracked in issue #210
_RASTER_EXTENSIONS = frozenset({".tif", ".tiff"})
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


def is_previewable(
    path: Path | str, relative_path: str, directory_prefixes: frozenset[str]
) -> bool:
    """Whether an archive file is to get a preview.

    Eligibility is a family/stage prefix match on the first two segments of the
    asset's mission-relative path
    """
    family_and_stage = "/".join(PurePath(relative_path).parts[:2])
    return family_and_stage in directory_prefixes and can_derive(path)


def dispatch_deriver(path: Path | str) -> DerivedPreview | None:
    """Route a file to its preview deriver by extension.

    sync and slow: the whole file is read to build the overview
    Async callers must run this in a worker thread
    Returns None for unsupported extensions and directories.
    """
    p = Path(path)
    if not can_derive(p):
        return None
    if p.suffix.lower() in _VECTOR_EXTENSIONS:
        return derive_vector_preview(p)
    if p.suffix.lower() in _KMALL_EXTENSIONS:
        return derive_kmall_preview(p)
    return derive_raster_preview(p)
