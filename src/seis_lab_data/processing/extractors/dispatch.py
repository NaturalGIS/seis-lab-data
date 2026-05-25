from pathlib import Path

from .schemas import RasterMetadata

_RASTER_EXTENSIONS = frozenset({".tif", ".tiff", ".xyz", ".asc", ".flt", ".nc", ".nc4"})


def dispatch_extractor(path: Path | str) -> RasterMetadata | None:
    p = Path(path)
    if p.suffix.lower() in _RASTER_EXTENSIONS:
        from .gdal_raster import extract_raster_metadata

        return extract_raster_metadata(p)
    return None
