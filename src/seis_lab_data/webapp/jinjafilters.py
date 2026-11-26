"""Custom jinja filters."""

import logging
import typing

import shapely
from jinja2 import pass_context
from jinja2.filters import do_filesizeformat
from osgeo import (
    ogr,
    osr,
)
from starlette_babel import gettext_lazy as _

from .. import constants

if typing.TYPE_CHECKING:
    from ..schemas import projects as project_schemas
    from ..schemas import surveymissions as mission_schemas
    from ..schemas import surveyrelatedrecords as record_schemas

    ItemWithStatus = typing.TypeVar(
        "ItemWithStatus",
        bound=(
            project_schemas.ProjectReadDetail,
            project_schemas.ProjectReadEmbedded,
            project_schemas.ProjectReadListItem,
            mission_schemas.SurveyMissionReadDetail,
            mission_schemas.SurveyMissionReadEmbedded,
            mission_schemas.SurveyMissionReadListItem,
            record_schemas.SurveyRelatedRecordReadDetail,
            record_schemas.SurveyRelatedRecordReadEmbedded,
            record_schemas.SurveyRelatedRecordReadListItem,
        ),
    )

logger = logging.getLogger(__name__)

# without it GDAL returns error values, such as a length of -1, instead of raising
osr.UseExceptions()

_WGS84_EPSG_CODE = 4326
# a shorter side of a native bbox would be shown as 0 m
_SHORTEST_NATIVE_SIDE_METRES = 0.5


@pass_context
def get_status_icon_name(
    context: dict[str, typing.Any],
    item: "ItemWithStatus",
) -> str:
    # only for draft and published items - the others get a spinner instead
    return {
        constants.ProjectStatus.DRAFT: context["icons"]["status_draft"],
        constants.ProjectStatus.PUBLISHED: context["icons"]["status_published"],
        constants.SurveyMissionStatus.DRAFT: context["icons"]["status_draft"],
        constants.SurveyMissionStatus.PUBLISHED: context["icons"]["status_published"],
        constants.SurveyRelatedRecordStatus.DRAFT: context["icons"]["status_draft"],
        constants.SurveyRelatedRecordStatus.PUBLISHED: context["icons"][
            "status_published"
        ],
    }[item.status]


def translate_enum(value: constants.TranslatableEnumProtocol) -> str:
    return value.get_translated_value()


def get_polygon_bounds(polygon_wkt: str) -> tuple[float, float, float, float]:
    geom = shapely.from_wkt(polygon_wkt)
    return geom.bounds


def get_discovery_info_items(discovery_info: dict | None) -> list[tuple[str, str]]:
    """List the translated name and the formatted value of a record's discovery info.

    There is an item for each key of `DiscoveryInfoKey` that the info holds, in the
    order of the enumeration. Only names are translated, as the values are
    technical identifiers.
    """
    if not discovery_info:
        return []
    return [
        (
            key.get_translated_value(),
            _format_discovery_info_item(key, discovery_info),
        )
        for key in constants.DiscoveryInfoKey
        if key.value in discovery_info
    ]


def _format_discovery_info_item(
    key: constants.DiscoveryInfoKey, discovery_info: dict
) -> str:
    value = discovery_info[key.value]
    if key == constants.DiscoveryInfoKey.FILE_SIZE_BYTES:
        return do_filesizeformat(value)
    if key == constants.DiscoveryInfoKey.CRS_NAME:
        crs = value
        if "epsg" in discovery_info:
            crs = f"{crs} - EPSG:{discovery_info['epsg']}"
        if discovery_info.get("crs_from_mission"):
            crs = f"{crs} ({_('from the survey mission')})"
        return crs
    if key == constants.DiscoveryInfoKey.WIDTH:
        return f"{value} x {discovery_info['height']}"
    if key == constants.DiscoveryInfoKey.PIXEL_SIZE_X:
        # GDAL gives a north-up raster a negative pixel height. No exponent, which
        # a pixel size in degrees would get for being so small
        return " x ".join(
            f"{abs(discovery_info[size_key]):.10f}".rstrip("0").rstrip(".")
            for size_key in ("pixel_size_x", "pixel_size_y")
        )
    # JSONB gives a large float back as an integer, e.g. the Float32 nodata
    if key == constants.DiscoveryInfoKey.NODATA:
        return f"{float(value):g}"
    if key == constants.DiscoveryInfoKey.POINT_COUNT:
        if discovery_info.get("point_count_estimated"):
            return f"{value} ({_('estimated')})"
        return str(value)
    if key == constants.DiscoveryInfoKey.ECHO_SOUNDER_ID:
        return f"EM {value}"
    if key == constants.DiscoveryInfoKey.DURATION_SECONDS:
        # in seconds under a minute, as "0 min" would read as no data
        return f"{round(value)} s" if value < 60 else f"{round(value / 60)} min"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        return ", ".join(f"{element:.8g}" for element in value)
    return str(value)


class BboxSize(typing.NamedTuple):
    width: str
    height: str
    diagonal: str
    area: str
    is_native_bbox: bool


def get_bbox_size(
    bbox_4326: shapely.Polygon | None, discovery_info: dict | None
) -> BboxSize | None:
    """Return the formatted size of a record's bounding box, None if it has none.

    The native bounding box of the data file is measured when it has an area.
    The WGS 84 one is larger than it away from the central meridian of the CRS.
    Any other record has its WGS 84 one measured, which is the one drawn on the map.
    """
    if bbox_4326 is None:
        return None
    size = _measure_native_bbox(discovery_info)
    is_native_bbox = size is not None
    if not is_native_bbox:
        size = _measure_bbox(bbox_4326.bounds, _WGS84_EPSG_CODE)
    width, height, diagonal, area = size
    return BboxSize(
        width=_format_length(width),
        height=_format_length(height),
        diagonal=_format_length(diagonal),
        area=_format_area(area),
        is_native_bbox=is_native_bbox,
    )


def _measure_native_bbox(
    discovery_info: dict | None,
) -> tuple[float, float, float, float] | None:
    """Return the size of the native bbox of a record, None if it has none to measure.

    A file with a single position, or a line along an axis, has a bbox without an area.
    Discovery adds a margin to its WGS 84 bbox, so that one has a size to show.
    """
    if not discovery_info:
        return None
    native_bounds = discovery_info.get("bbox_native")
    native_epsg_code = discovery_info.get("epsg")
    if native_bounds is None or native_epsg_code is None:
        return None
    size = _measure_bbox(native_bounds, native_epsg_code)
    width, height, _diagonal, _area = size
    if min(width, height) < _SHORTEST_NATIVE_SIDE_METRES:
        return None
    return size


def _measure_bbox(
    bounds: typing.Sequence[float], epsg_code: int
) -> tuple[float, float, float, float]:
    """Return the width, height, diagonal and area of a bbox, measured in metres.

    GDAL measures on the ellipsoid of the CRS, so any unit of the CRS gives metres.
    """
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    # x before y, as GDAL reads the coordinates of some CRSs as y before x
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    min_x, min_y, max_x, max_y = bounds
    # the width of a bbox in degrees changes with the latitude, so the middle is used
    middle_y = (min_y + max_y) / 2
    width_line = shapely.LineString([(min_x, middle_y), (max_x, middle_y)])
    height_line = shapely.LineString([(min_x, min_y), (min_x, max_y)])
    diagonal_line = shapely.LineString([(min_x, min_y), (max_x, max_y)])
    return (
        _convert_to_ogr_geometry(width_line, srs).GeodesicLength(),
        _convert_to_ogr_geometry(height_line, srs).GeodesicLength(),
        _convert_to_ogr_geometry(diagonal_line, srs).GeodesicLength(),
        _convert_to_ogr_geometry(shapely.box(*bounds), srs).GeodesicArea(),
    )


def _convert_to_ogr_geometry(
    geometry: shapely.Geometry, srs: osr.SpatialReference
) -> ogr.Geometry:
    """Return a shapely geometry as an OGR one in the given CRS."""
    ogr_geometry = ogr.CreateGeometryFromWkb(shapely.to_wkb(geometry))
    ogr_geometry.AssignSpatialReference(srs)
    return ogr_geometry


def _format_length(metres: float) -> str:
    # in kilometres from 1 km on, as long lengths in metres are hard to read
    if metres < 1000:
        return f"{metres:.0f} m"
    return f"{metres / 1000:.2f} km"


def _format_area(square_metres: float) -> str:
    if square_metres < 1_000_000:
        return f"{square_metres:.0f} m²"
    return f"{square_metres / 1_000_000:.2f} km²"
