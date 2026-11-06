import functools
import re

from osgeo import osr
from starlette_babel import gettext_lazy as _

from ..schemas.common import parse_epsg_code

_MAX_SUGGESTIONS = 15

_SUGGESTED_CRS_TYPES = (
    osr.OSR_CRS_TYPE_PROJECTED,
    osr.OSR_CRS_TYPE_GEOGRAPHIC_2D,
    osr.OSR_CRS_TYPE_GEOGRAPHIC_3D,
)


@functools.cache
def _load_suggested_epsg_codes() -> tuple[tuple[str, str], ...]:
    # deprecated codes are hidden so nobody browses into a superseded definition
    # parse_epsg_code still accepts them, and compound codes, when typed by hand
    return tuple(
        (crs_info.code, crs_info.name)
        for crs_info in osr.GetCRSInfoListFromDatabase("EPSG")
        if crs_info.type in _SUGGESTED_CRS_TYPES and not crs_info.deprecated
    )


def find_epsg_code_suggestions(search_value: str) -> list[tuple[str, str]]:
    """Return (code, name) pairs matching the search value by code prefix or name.

    Code matches come first, otherwise names like "... zone 37" push the 37xx out.
    """
    search_value = search_value.strip()
    if not search_value:
        return []
    lowered_search_value = search_value.lower()
    suggested_codes = _load_suggested_epsg_codes()
    code_matches = [
        (code, name) for code, name in suggested_codes if code.startswith(search_value)
    ]
    name_matches = [
        (code, name)
        for code, name in suggested_codes
        if not code.startswith(search_value) and lowered_search_value in name.lower()
    ]
    return (code_matches + name_matches)[:_MAX_SUGGESTIONS]


def extract_epsg_code(raw_value: str) -> int:
    """Return the EPSG code at the start of a typed value, e.g. "3763 - name"."""
    code_match = re.match(r"\s*\+?(\d+)", raw_value)
    if code_match is None:
        raise ValueError(_("Enter a numeric EPSG code"))
    return int(code_match.group(1))


def get_epsg_crs_name(raw_value: str) -> str:
    """Return the name of the CRS behind a typed EPSG code.

    Raises ValueError with a message for the user when the value is not a usable code.
    """
    epsg_code = extract_epsg_code(raw_value)
    try:
        parse_epsg_code(epsg_code)
    except ValueError as err:
        raise ValueError(
            _("Unknown EPSG code, or not a projected or geographic CRS")
        ) from err
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(epsg_code)
    return spatial_reference.GetName()
