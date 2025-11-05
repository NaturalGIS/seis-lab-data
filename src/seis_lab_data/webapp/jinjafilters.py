"""Custom jinja filters."""

import logging
import typing

import shapely
from jinja2 import pass_context

from ..constants import (
    ProjectStatus,
    TranslatableEnumProtocol,
)
from ..schemas.common import Localizable

logger = logging.getLogger(__name__)


@pass_context
def translate_localizable_string(
    context: dict[str, typing.Any], value: Localizable
) -> str:
    current_lang = context["request"].state.language
    return getattr(value, current_lang, value.en) or ""


@pass_context
def get_status_icon_name(context: dict[str, typing.Any], status: ProjectStatus) -> str:
    return {
        ProjectStatus.DRAFT: context.get("icons", {}).get("status_draft", ""),
        ProjectStatus.UNDER_VALIDATION: context.get("icons", {}).get(
            "status_under_validation", ""
        ),
        ProjectStatus.PUBLISHED: context.get("icons", {}).get("status_published", ""),
    }.get(status, "")


def translate_enum(value: TranslatableEnumProtocol) -> str:
    return value.get_translated_value()


def get_polygon_bounds(polygon_wkt: str) -> tuple[float, float, float, float]:
    geom = shapely.from_wkt(polygon_wkt)
    return geom.bounds
