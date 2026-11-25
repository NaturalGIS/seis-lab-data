import datetime as dt
import re
from pathlib import Path

import shapely
from osgeo import osr

from . import common
from .schemas import ExtractedMetadata

# the last section of the text header started by byte 309,056 in the files seen
_HEAD_BYTES = 1024 * 1024
# the header section starts at byte 17 in every file seen
_HEADER_SEARCH_BYTES = 64
# a point of the planned line holds a number, then its x and y in the file's CRS
_POINT_LINE = re.compile(rb"^Point\(\d+\) = [^,\n]*,([^,\n]*),([^,\n]*)", re.MULTILINE)
_PORTUGAL_TM06_EPSG_CODE = 3763
# the PDS key of each projection parameter, by its name in GDAL
_PROJECTION_PARAMETER_KEYS = {
    osr.SRS_PP_LATITUDE_OF_ORIGIN: b"LatOrigin",
    osr.SRS_PP_CENTRAL_MERIDIAN: b"LonOrigin",
    osr.SRS_PP_FALSE_EASTING: b"FalseEast",
    osr.SRS_PP_FALSE_NORTHING: b"FalseNorth",
    osr.SRS_PP_SCALE_FACTOR: b"ScaleConst",
}
# the files seen write the origin with 14 digits, so it is not exactly the EPSG value
_PARAMETER_TOLERANCE = 1e-9


def extract_pds_metadata(path: Path | str) -> ExtractedMetadata:
    """Extract metadata from the text header of a Teledyne PDS file.

    The format is closed, so only the text header at the start of the file is read.
    Its sections have binary tags between them, so it is searched and not parsed as INI.
    The temporal extent is the day the acquisition started, as no end time is recorded.
    The CRS is only recognised for WGS 84 / UTM and ETRS89 / Portugal TM06.
    A file in any other CRS gets no CRS and no bbox.
    The bbox is the planned survey area of the run line, as the positions are binary.
    Raises ValueError if the file does not start with a PDS header.
    """
    p = Path(path)
    with p.open("rb") as fh:
        head = fh.read(_HEAD_BYTES)
    if b"[HEADER]" not in head[:_HEADER_SEARCH_BYTES]:
        raise ValueError(f"{p.name} does not look like a Teledyne PDS file")
    # the PDS 3.9 files seen end their lines with CRLF
    text = head.replace(b"\r\n", b"\n")
    srs = _spatial_reference(text)
    epsg, crs_name, crs_wkt = common.identify_srs(srs)
    bbox_native = None
    bbox_4326 = None
    # without a CRS, discovery would place a native bbox with the mission's CRS
    if srs is not None:
        bbox_native = _planned_area_bounds(text)
    if bbox_native is not None:
        bbox_4326 = common.project_bbox_to_wgs84(bbox_native, srs)
    start_date = _acquisition_start_date(text)
    return ExtractedMetadata(
        driver="Teledyne PDS",
        epsg=epsg,
        crs_name=crs_name,
        crs_wkt=crs_wkt,
        bbox_native=bbox_native,
        bbox_4326=bbox_4326,
        # no end time is recorded, and records only store dates with both ends
        temporal_extent_begin=start_date,
        temporal_extent_end=start_date,
    )


def _spatial_reference(text: bytes) -> osr.SpatialReference | None:
    """Return the spatial reference of a header, None if its CRS is not recognised.

    WGS 84 / UTM and ETRS89 / Portugal TM06 are recognised, by their parameters.
    The name of the CRS is not used, as it is free text.
    """
    # "medthod" is how the files spell it
    projection_method = _value_of_key(text, b"Projection medthod")
    ellipsoid = _value_of_key(text, b"Ellipsoid name")
    is_utm = projection_method == b"Universal Transverse Mercator"
    is_transverse_mercator = projection_method == b"Transverse Mercator"
    if is_utm and ellipsoid == b"WGS84":
        return _utm_spatial_reference(text)
    if is_transverse_mercator and ellipsoid == b"GRS 1980":
        return _portugal_tm06_spatial_reference(text)
    return None


def _utm_spatial_reference(text: bytes) -> osr.SpatialReference | None:
    """Return the WGS 84 / UTM zone of a header, None if its parameters give none.

    GDAL finds the zone from the projection parameters of the header.
    """
    described = osr.SpatialReference()
    described.SetWellKnownGeogCS("WGS84")
    described.SetProjection(osr.SRS_PT_TRANSVERSE_MERCATOR)
    for parameter_name, pds_key in _PROJECTION_PARAMETER_KEYS.items():
        header_value = _number_of_key(text, pds_key)
        if header_value is None:
            return None
        described.SetProjParm(parameter_name, header_value)
    # GDAL gives zone 0 when the parameters are not the ones of a UTM zone
    if described.GetUTMZone() == 0:
        return None
    described.AutoIdentifyEPSG()
    epsg_code = int(described.GetAuthorityCode(None))
    # imported by its code, as a CRS built from parameters has no name
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    return srs


def _portugal_tm06_spatial_reference(text: bytes) -> osr.SpatialReference | None:
    """Return ETRS89 / Portugal TM06, None if the header is in another CRS.

    Every projection parameter of the header has to match the one of this CRS.
    """
    portugal_tm06 = osr.SpatialReference()
    portugal_tm06.ImportFromEPSG(_PORTUGAL_TM06_EPSG_CODE)
    for parameter_name, pds_key in _PROJECTION_PARAMETER_KEYS.items():
        expected_value = portugal_tm06.GetProjParm(parameter_name)
        header_value = _number_of_key(text, pds_key)
        if header_value is None:
            return None
        difference = abs(header_value - expected_value)
        if difference > _PARAMETER_TOLERANCE:
            return None
    return portugal_tm06


def _planned_area_bounds(text: bytes) -> tuple[float, float, float, float] | None:
    """Return the bounds of the planned survey area of the run line, in the file's CRS.

    The planned line is widened on both sides by the wider side of its box.
    Returns None if the line or the box widths are missing or not numbers.
    """
    section = _planned_pattern_section(text)
    if section is None:
        return None
    width_left = _number_of_key(section, b"ParBoxWidthL")
    width_right = _number_of_key(section, b"ParBoxWidthR")
    if width_left is None or width_right is None:
        return None
    try:
        points = [(float(x), float(y)) for x, y in _POINT_LINE.findall(section)]
    except ValueError:
        return None
    if len(points) < 2:
        return None
    # the side of the line each width is on is not known, so the wider one goes on both
    width = max(width_left, width_right)
    # flat ends, as the box does not go past the ends of the line
    planned_area = shapely.LineString(points).buffer(width, cap_style="flat")
    if planned_area.is_empty:
        return None
    return planned_area.bounds


def _planned_pattern_section(text: bytes) -> bytes | None:
    """Return the section of a header holding the planned pattern of its run line.

    The section is named after the run line up to its first dot.
    Returns None if the header has no run line or no such section.
    """
    runline_name = _value_of_key(text, b"RunlineName")
    if runline_name is None:
        return None
    section_header = b"[" + runline_name.split(b".")[0] + b"]\n"
    # not anchored to a line start, as PDS 4.1 glues a binary tag before the header
    # the section runs to its first blank line
    section = re.search(re.escape(section_header) + rb"((?:.+\n)*)", text)
    return section.group(1) if section else None


def _value_of_key(text: bytes, key: bytes) -> bytes | None:
    """Return the value of the first `key = value` line of `text`, None if none."""
    line = re.search(rb"^" + re.escape(key) + rb" = (.*)$", text, re.MULTILINE)
    return line.group(1).strip() if line else None


def _number_of_key(text: bytes, key: bytes) -> float | None:
    """Return the value of `key` as a number, None if it is missing or not a number."""
    value = _value_of_key(text, key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _acquisition_start_date(text: bytes) -> dt.date | None:
    """Return the day the acquisition started, None if it is missing or malformed."""
    start_time = _value_of_key(text, b"AcquisLogStartTime")
    if start_time is None:
        return None
    try:
        return dt.datetime.strptime(start_time.decode(), "%Y%m%d-%H%M%S").date()
    except ValueError:
        return None
