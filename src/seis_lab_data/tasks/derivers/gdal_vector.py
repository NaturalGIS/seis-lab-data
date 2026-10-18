import logging
from pathlib import Path

from osgeo import gdal

from . import common
from .schemas import DerivedPreview

logger = logging.getLogger(__name__)

gdal.UseExceptions()

# Degrees added to every side of the extent (~10 m, same spirit as discovery's
# bbox buffer), keeps degenerate point and line extents rasterisable and edge
# features off the image border
_BOUNDS_MARGIN = 1e-4
# A strong red that reads over the bathymetry base map; one colour for every
# layer in v1 Style is still to be decided later
_BURN_RGBA = (230, 57, 70, 255)


def derive_vector_preview(path: Path | str) -> DerivedPreview:
    """Rasterise a vector as a small transparent WEBP image, in EPSG:4326.

    Only vectors which declare their own CRS are handled, a survey mission's
    implicit CRS is not applied here.

    Pure sync and potentially slow (every feature is read and reprojected in
    memory), so async callers must run this in a worker thread (e.g.
    anyio.to_thread.run_sync).
    """
    ds = gdal.OpenEx(str(path), gdal.OF_VECTOR | gdal.OF_READONLY)
    try:
        layer_names = []
        has_features = False
        for layer_index in range(ds.GetLayerCount()):
            lyr = ds.GetLayer(layer_index)
            if lyr.GetFeatureCount() <= 0:
                continue
            has_features = True
            if lyr.GetSpatialRef() is not None:
                layer_names.append(lyr.GetName())
        if not has_features:
            raise ValueError(f"Vector {path} has no features to render")
        if not layer_names:
            raise ValueError(f"Vector {path} does not declare a CRS")
        # one explicit reprojection, the canvas below shares its CRS, so the
        # rasterisation transforms nothing
        translated = gdal.VectorTranslate(
            "",
            ds,
            format="MEM",
            dstSRS="EPSG:4326",
            reproject=True,
            layers=layer_names,
        )
        boxes = []
        for layer_index in range(translated.GetLayerCount()):
            # can_return_null a layer holding only null geometries would
            # otherwise report (0, 0, 0, 0) and drag the canvas to null island
            extent = translated.GetLayer(layer_index).GetExtent(
                force=1, can_return_null=True
            )
            if extent is None:
                continue
            # OGR GetExtent returns (minx, maxx, miny, maxy); reorder it.
            minx, maxx, miny, maxy = extent
            boxes.append((minx, miny, maxx, maxy))
        if not boxes:
            raise ValueError(f"Vector {path} has no geometries to render")
        min_x = min(box[0] for box in boxes) - _BOUNDS_MARGIN
        min_y = min(box[1] for box in boxes) - _BOUNDS_MARGIN
        max_x = max(box[2] for box in boxes) + _BOUNDS_MARGIN
        max_y = max(box[3] for box in boxes) + _BOUNDS_MARGIN
        # like the warped rasters, the longest side gets the
        # full preview size and the other follows the ratio of the spans
        scale = common.MAX_PREVIEW_PIXELS / max(max_x - min_x, max_y - min_y)
        width = max(1, round((max_x - min_x) * scale))
        height = max(1, round((max_y - min_y) * scale))
        rgba = gdal.Rasterize(
            "",
            translated,
            format="MEM",
            outputType=gdal.GDT_Byte,
            width=width,
            height=height,
            outputBounds=[min_x, min_y, max_x, max_y],
            outputSRS="EPSG:4326",
            # one band per burn value, so the canvas is RGBA and whatever is
            # not burnt stays (0, 0, 0, 0), transparent
            burnValues=list(_BURN_RGBA),
            # every pixel a line crosses is burnt, so thin lines stay
            # continuous at preview size
            allTouched=True,
            layers=layer_names,
        )
        # the bounds are the canvas's, padding included, or the map overlay
        # misregisters
        return DerivedPreview(
            image=common.to_webp(rgba), bounds_4326=(min_x, min_y, max_x, max_y)
        )
    finally:
        # Clear / close gdal used datasets
        rgba = None  # noqa: F841
        translated = None  # noqa: F841
        ds = None  # noqa: F841
