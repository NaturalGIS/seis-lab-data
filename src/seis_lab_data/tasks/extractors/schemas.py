import datetime as dt

import pydantic

from ... import constants


def _format_crs(epsg: int | None, crs_name: str | None) -> str:
    if crs_name and epsg is not None:
        return f"{crs_name} (EPSG:{epsg})"
    if epsg is not None:
        return f"EPSG:{epsg}"
    if crs_name:
        return crs_name
    return "unknown"


def _native_bbox_clause(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return ""
    minx, miny, maxx, maxy = bbox
    return f" Native bbox: {minx:.8g}, {miny:.8g}, {maxx:.8g}, {maxy:.8g}."


class ExtractedMetadata(pydantic.BaseModel):
    driver: str | None = None
    epsg: int | None = None
    crs_name: str | None = None
    crs_wkt: str | None = None
    bbox_native: tuple[float, float, float, float] | None = None
    bbox_4326: tuple[float, float, float, float] | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None

    def describe(self) -> str:
        raise NotImplementedError


class RasterMetadata(ExtractedMetadata):
    width: int
    height: int
    band_count: int
    pixel_size_x: float | None = None
    pixel_size_y: float | None = None
    nodata: float | None = None

    def describe(self) -> str:
        summary = (
            f"Auto-extracted: {self.driver} raster, "
            f"{self.width} x {self.height} px, {self.band_count} band(s)"
        )
        if self.pixel_size_x is not None and self.pixel_size_y is not None:
            summary += (
                f", pixel size {abs(self.pixel_size_x):g} x {abs(self.pixel_size_y):g}"
            )
        if self.nodata is not None:
            summary += f", nodata {self.nodata:g}"
        summary += f". CRS: {_format_crs(self.epsg, self.crs_name)}."
        summary += _native_bbox_clause(self.bbox_native)
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


class VectorMetadata(ExtractedMetadata):
    layer_count: int
    feature_count: int
    geometry_type: str

    def describe(self) -> str:
        summary = (
            f"Auto-extracted: {self.driver} vector, {self.layer_count} layer(s), "
            f"{self.feature_count} feature(s), geometry: {self.geometry_type}. "
            f"CRS: {_format_crs(self.epsg, self.crs_name)}."
        )
        summary += _native_bbox_clause(self.bbox_native)
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


ExtractionResult = RasterMetadata | VectorMetadata
