import datetime as dt
import typing

import pydantic

from ... import constants

# The natural-language words that go into describe(), per language. Keys are
# identical across languages (a parity test enforces it). Counts keep the
# literal "(s)" convention in both languages rather than resolving plurals.
# Technical identifiers stay in English on purpose and are NOT here: driver
# names, geometry types, sample-format codes, "CRS", "nodata", "px", "EM <id>",
# "Kongsberg KMALL" and "SEG-Y".
_WORDS: dict[str, dict[str, str]] = {
    "en": {
        "auto_extracted": "Auto-extracted",
        "raster_kind": "{driver} raster",
        "vector_kind": "{driver} vector",
        "bands": "band(s)",
        "pixel_size": "pixel size",
        "layers": "layer(s)",
        "features": "feature(s)",
        "geometry": "geometry",
        "unknown_sounder": "unknown sounder",
        "datagrams": "datagram(s)",
        "position_fixes": "position fix(es)",
        "traces": "trace(s)",
        "samples_per_trace": "sample(s) per trace",
        "sample_interval": "sample interval {value} (raw)",
        "coordinates_in": "coordinates in",
        "partly_unreliable": "Coordinate sampling was partly unreliable.",
        "crs_unknown": "unknown",
        "native_bbox": "Native bbox",
    },
    "pt": {
        "auto_extracted": "Extração automática",
        "raster_kind": "raster {driver}",
        "vector_kind": "vetor {driver}",
        "bands": "banda(s)",
        "pixel_size": "tamanho do pixel",
        "layers": "camada(s)",
        "features": "elemento(s)",
        "geometry": "geometria",
        "unknown_sounder": "sonda desconhecida",
        "datagrams": "datagrama(s)",
        "position_fixes": "posição(ões)",
        "traces": "traço(s)",
        "samples_per_trace": "amostra(s) por traço",
        "sample_interval": "intervalo de amostragem {value} (bruto)",
        "coordinates_in": "coordenadas em",
        "partly_unreliable": ("A amostragem de coordenadas foi parcial, pouco fiável."),
        "crs_unknown": "desconhecido",
        "native_bbox": "Extensão nativa",
    },
}

# The closed set of SEG-Y coordinate-unit labels that translate; "dms" and the
# dynamic "code N" fallback pass through unchanged. A test pins that every
# segy._UNITS_LABELS value except "dms" has an entry here.
_UNITS_PT = {
    "unset": "unidades desconhecidas",
    "metres": "metros",
    "arc-seconds": "segundos de arco",
    "degrees": "graus",
}


def _format_crs(epsg: int | None, crs_name: str | None, language: str) -> str:
    if crs_name and epsg is not None:
        return f"{crs_name} (EPSG:{epsg})"
    if epsg is not None:
        return f"EPSG:{epsg}"
    if crs_name:
        return crs_name
    return _WORDS[language]["crs_unknown"]


def _native_bbox_clause(
    bbox: tuple[float, float, float, float] | None, language: str
) -> str:
    if bbox is None:
        return ""
    minx, miny, maxx, maxy = bbox
    label = _WORDS[language]["native_bbox"]
    return f" {label}: {minx:.8g}, {miny:.8g}, {maxx:.8g}, {maxy:.8g}."


class ExtractedMetadata(pydantic.BaseModel):
    driver: str | None = None
    epsg: int | None = None
    crs_name: str | None = None
    crs_wkt: str | None = None
    bbox_native: tuple[float, float, float, float] | None = None
    bbox_4326: tuple[float, float, float, float] | None = None
    temporal_extent_begin: dt.date | None = None
    temporal_extent_end: dt.date | None = None

    def describe(self, language: typing.Literal["en", "pt"] = "en") -> str:
        raise NotImplementedError


class RasterMetadata(ExtractedMetadata):
    width: int
    height: int
    band_count: int
    pixel_size_x: float | None = None
    pixel_size_y: float | None = None
    nodata: float | None = None

    def describe(self, language: typing.Literal["en", "pt"] = "en") -> str:
        words = _WORDS[language]
        summary = (
            f"{words['auto_extracted']}: "
            f"{words['raster_kind'].format(driver=self.driver)}, "
            f"{self.width} x {self.height} px, {self.band_count} {words['bands']}"
        )
        if self.pixel_size_x is not None and self.pixel_size_y is not None:
            summary += (
                f", {words['pixel_size']} "
                f"{abs(self.pixel_size_x):g} x {abs(self.pixel_size_y):g}"
            )
        if self.nodata is not None:
            summary += f", nodata {self.nodata:g}"
        summary += f". CRS: {_format_crs(self.epsg, self.crs_name, language)}."
        summary += _native_bbox_clause(self.bbox_native, language)
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


class VectorMetadata(ExtractedMetadata):
    layer_count: int
    feature_count: int
    geometry_type: str

    def describe(self, language: typing.Literal["en", "pt"] = "en") -> str:
        words = _WORDS[language]
        summary = (
            f"{words['auto_extracted']}: "
            f"{words['vector_kind'].format(driver=self.driver)}, "
            f"{self.layer_count} {words['layers']}, "
            f"{self.feature_count} {words['features']}, "
            f"{words['geometry']}: {self.geometry_type}. "
            f"CRS: {_format_crs(self.epsg, self.crs_name, language)}."
        )
        summary += _native_bbox_clause(self.bbox_native, language)
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


class KmallMetadata(ExtractedMetadata):
    echo_sounder_id: int | None = None
    datagram_count: int
    position_count: int

    def describe(self, language: typing.Literal["en", "pt"] = "en") -> str:
        words = _WORDS[language]
        sounder = (
            f"EM {self.echo_sounder_id}"
            if self.echo_sounder_id
            else words["unknown_sounder"]
        )
        summary = (
            f"{words['auto_extracted']}: Kongsberg KMALL, {sounder}, "
            f"{self.datagram_count} {words['datagrams']}, "
            f"{self.position_count} {words['position_fixes']}. "
            f"CRS: {_format_crs(self.epsg, self.crs_name, language)}."
        )
        summary += _native_bbox_clause(self.bbox_native, language)
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

    def describe(self, language: typing.Literal["en", "pt"] = "en") -> str:
        words = _WORDS[language]
        summary = f"{words['auto_extracted']}: SEG-Y"
        if self.trace_count is not None:
            summary += f", {self.trace_count} {words['traces']}"
        if self.samples_per_trace is not None:
            summary += f", {self.samples_per_trace} {words['samples_per_trace']}"
        if self.sample_interval is not None:
            summary += (
                f", {words['sample_interval'].format(value=self.sample_interval)}"
            )
        if self.sample_format is not None:
            summary += f", {self.sample_format}"
        if self.coordinate_units is not None:
            units = self.coordinate_units
            if language == "pt":
                units = _UNITS_PT.get(units, units)
            summary += f", {words['coordinates_in']} {units}"
        summary += f". CRS: {_format_crs(self.epsg, self.crs_name, language)}."
        summary += _native_bbox_clause(self.bbox_native, language)
        if self.coverage == "partial":
            summary += f" {words['partly_unreliable']}"
        return summary[: constants.DESCRIPTION_MAX_LENGTH]


ExtractionResult = RasterMetadata | VectorMetadata | KmallMetadata | SegyMetadata
