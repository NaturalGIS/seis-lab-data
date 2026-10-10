import logging
import math
import uuid
from pathlib import Path

from osgeo import gdal

from . import common
from .schemas import DerivedPreview

logger = logging.getLogger(__name__)

gdal.UseExceptions()

# Percentile stretch, cumulative count cut: the extremes of a
# bathymetry grid are almost always outliers and a min/max stretch washes the
# image out.
_HISTOGRAM_BUCKETS = 256
_LOWER_PERCENTILE = 0.02
_UPPER_PERCENTILE = 0.98
# Single-band rasters render with the turbo colour ramp, the one the IPMA team
# applies in QGIS. The values are matplotlib's turbo table sampled at 17
# points, as (fraction, r, g, b). gdaldem interpolates linearly between stops.
_TURBO_RAMP = (
    (0.0, 48, 18, 59),
    (0.0625, 64, 64, 162),
    (0.125, 70, 107, 227),
    (0.1875, 66, 148, 255),
    (0.25, 40, 188, 235),
    (0.3125, 24, 221, 194),
    (0.375, 50, 242, 152),
    (0.4375, 109, 254, 98),
    (0.5, 164, 252, 60),
    (0.5625, 203, 237, 52),
    (0.625, 236, 209, 58),
    (0.6875, 253, 174, 53),
    (0.75, 251, 129, 34),
    (0.8125, 236, 83, 15),
    (0.875, 210, 49, 5),
    (0.9375, 172, 23, 1),
    (1.0, 122, 4, 3),
)


def derive_raster_preview(path: Path | str) -> DerivedPreview:
    """Render a raster as a small WEBP image, warped to EPSG:4326.

    Only rasters which declare their own CRS are handled, a survey mission's
    implicit CRS is not applied here.

    Pure sync and potentially slow (the whole raster is read once in order to
    build the overview), so async callers must run this in a worker thread (e.g.
    anyio.to_thread.run_sync).
    """
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    try:
        # `dataset` stays referenced for the whole function: GDAL garbage
        # collects the dataset from under its own bands otherwise
        if dataset.RasterCount == 0:
            raise ValueError(f"Raster {path} has no bands")
        if not dataset.GetProjection():
            raise ValueError(f"Raster {path} does not declare a CRS")
        if (
            dataset.RasterCount == 1
            and dataset.GetRasterBand(1).GetRasterColorTable() is not None
        ):
            # palette indices can be neither resampled nor stretched, expand
            # to RGB before warping
            dataset = gdal.Translate("", dataset, format="MEM", rgbExpand="rgb")
        nodata = dataset.GetRasterBand(1).GetNoDataValue()
        width, height = _preview_size(dataset.RasterXSize, dataset.RasterYSize)
        warped = gdal.Warp(
            "",
            dataset,
            format="MEM",
            dstSRS="EPSG:4326",
            width=width,
            height=height,
            resampleAlg="average",
            # without the nodata pair the areas the warp fills with 0 enter the
            # statistics below and flatten the stretch; dstAlpha turns both the
            # fill and the source's own nodata into transparency
            srcNodata=nodata,
            dstNodata=nodata,
            dstAlpha=True,
        )
        bounds = _bounds(warped)
        alpha_band = warped.RasterCount
        if nodata is not None:
            for band_index in range(1, alpha_band):
                warped.GetRasterBand(band_index).SetNoDataValue(nodata)
        if dataset.RasterCount >= 3:
            if dataset.GetRasterBand(1).DataType == gdal.GDT_Byte:
                rgba = gdal.Translate(
                    "",
                    warped,
                    format="MEM",
                    outputType=gdal.GDT_Byte,
                    bandList=[1, 2, 3, alpha_band],
                )
            else:
                # a bare cast would clamp values above 255 instead of scaling
                # them, rendering 16-bit and float imagery as solid white
                scale_params = [
                    list(_percentile_cuts(warped.GetRasterBand(index))) + [1, 255]
                    for index in (1, 2, 3)
                ]
                rgba = gdal.Translate(
                    "",
                    warped,
                    format="MEM",
                    outputType=gdal.GDT_Byte,
                    bandList=[1, 2, 3, alpha_band],
                    scaleParams=scale_params + [[0, 255, 0, 255]],
                )
        else:
            low, high = _percentile_cuts(warped.GetRasterBand(1))
            # the ramp spans the percentile cuts, values beyond them take the
            # end colours; the colour table lives in GDAL's virtual memory,
            # never on disk
            vsi_color_path = f"/vsimem/{uuid.uuid4().hex}.txt"
            gdal.FileFromMemBuffer(
                vsi_color_path,
                "\n".join(
                    f"{low + fraction * (high - low)} {r} {g} {b}"
                    for fraction, r, g, b in _TURBO_RAMP
                ),
            )
            try:
                colored = gdal.DEMProcessing(
                    "",
                    warped,
                    processing="color-relief",
                    colorFilename=vsi_color_path,
                    format="MEM",
                )
            finally:
                gdal.Unlink(vsi_color_path)
            # the warp's alpha covers nodata and fill alike; separate=True
            # stacks all bands of each input, so the warped bands follow R, G, B
            stacked = gdal.BuildVRT("", [colored, warped], separate=True)
            rgba = gdal.Translate(
                "",
                stacked,
                format="MEM",
                outputType=gdal.GDT_Byte,
                bandList=[1, 2, 3, 3 + alpha_band],
            )
        return DerivedPreview(image=common.to_webp(rgba), bounds_4326=bounds)
    finally:
        # Clear / close gdal used datasets
        rgba = None  # noqa: F841
        stacked = None  # noqa: F841
        colored = None  # noqa: F841
        warped = None  # noqa: F841
        dataset = None  # noqa: F841


def _preview_size(width: int, height: int) -> tuple[int, int]:
    longest_side = max(width, height)
    if longest_side <= common.MAX_PREVIEW_PIXELS:
        return width, height
    scale = common.MAX_PREVIEW_PIXELS / longest_side
    return max(1, round(width * scale)), max(1, round(height * scale))


def _bounds(dataset) -> tuple[float, float, float, float]:
    # the warped dataset is always north-up, so the corners come straight out of
    # the geotransform
    gt = dataset.GetGeoTransform()
    min_x = gt[0]
    max_y = gt[3]
    max_x = gt[0] + dataset.RasterXSize * gt[1]
    min_y = gt[3] + dataset.RasterYSize * gt[5]
    if max_x <= min_x or max_y <= min_y:
        raise ValueError("Warped raster has an empty extent")
    return min_x, min_y, max_x, max_y


def _percentile_cuts(band) -> tuple[float, float]:
    """Find the values to stretch from.

    Nodata pixels take part in neither the range nor the histogram, so the cut
    points come from the raster's real values.
    """
    minimum, maximum = band.ComputeRasterMinMax(False)
    if not (math.isfinite(minimum) and math.isfinite(maximum)) or minimum >= maximum:
        raise ValueError("Raster has no usable value range")
    histogram = band.GetHistogram(minimum, maximum, _HISTOGRAM_BUCKETS, approx_ok=0)
    total = sum(histogram)
    if total == 0:
        raise ValueError("Raster has no valid pixels")
    bucket_width = (maximum - minimum) / _HISTOGRAM_BUCKETS
    lower_count = total * _LOWER_PERCENTILE
    upper_count = total * _UPPER_PERCENTILE
    low = high = None
    cumulative = 0
    for bucket_index, count in enumerate(histogram):
        previous = cumulative
        cumulative += count
        if low is None and previous < lower_count <= cumulative:
            low = minimum + bucket_index * bucket_width
        if high is None and previous < upper_count <= cumulative:
            high = minimum + (bucket_index + 1) * bucket_width
    if low is None or high is None or high <= low:
        return minimum, maximum
    return low, high
