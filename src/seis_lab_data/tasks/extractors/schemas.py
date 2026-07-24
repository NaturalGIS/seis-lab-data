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


class KmallMetadata(ExtractedMetadata):
    echo_sounder_id: int | None = None
    datagram_count: int
    position_count: int

    def describe(self) -> str:
        sounder = (
            f"EM {self.echo_sounder_id}" if self.echo_sounder_id else "unknown sounder"
        )
        summary = (
            f"Auto-extracted: Kongsberg KMALL, {sounder}, "
            f"{self.datagram_count} datagram(s), "
            f"{self.position_count} position fix(es). "
            f"CRS: {_format_crs(self.epsg, self.crs_name)}."
        )
        summary += _native_bbox_clause(self.bbox_native)
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


class SegyMetadata(ExtractedMetadata):
    trace_count: int | None = None
    samples_per_trace: int | None = None
    # the raw header value, deliberately unitless: time files store microseconds
    # here but depth-domain files store a length (50 == 0.05 m) and rev0/1 has
    # no flag to tell them apart
    sample_interval: int | None = None
    sample_format: str | None = None
    coordinate_units: str | None = None
    coverage: str = "full"

    def describe(self) -> str:
        summary = "Auto-extracted: SEG-Y"
        if self.trace_count is not None:
            summary += f", {self.trace_count} trace(s)"
        if self.samples_per_trace is not None:
            summary += f", {self.samples_per_trace} sample(s) per trace"
        if self.sample_interval is not None:
            summary += f", sample interval {self.sample_interval} (raw)"
        if self.sample_format is not None:
            summary += f", {self.sample_format}"
        if self.coordinate_units is not None:
            summary += f", coordinates in {self.coordinate_units}"
        summary += f". CRS: {_format_crs(self.epsg, self.crs_name)}."
        summary += _native_bbox_clause(self.bbox_native)
        if self.coverage == "partial":
            summary += " Coordinate sampling was partly unreliable."
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


ExtractionResult = RasterMetadata | VectorMetadata | KmallMetadata | SegyMetadata
