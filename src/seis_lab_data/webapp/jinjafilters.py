"""Custom jinja filters."""

import logging
import typing

import shapely
from jinja2 import pass_context
from jinja2.filters import do_filesizeformat
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


def discovery_info_items(discovery_info: dict | None) -> list[tuple[str, str]]:
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
