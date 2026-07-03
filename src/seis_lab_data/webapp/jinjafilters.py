"""Custom jinja filters."""

import json
import logging
import typing

import shapely
from jinja2 import pass_context
from markupsafe import Markup
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer

from ..constants import (
    ProjectStatus,
    TranslatableEnumProtocol,
)
from ..schemas.common import Localizable
from ..localization import translate_localizable

if typing.TYPE_CHECKING:
    from ..config import SeisLabDataSettings
    from ..schemas import surveyrelatedrecords as record_schemas

logger = logging.getLogger(__name__)


@pass_context
def get_secondary_language_value(
    context: dict[str, typing.Any], value: Localizable
) -> str:
    current_lang = context["request"].state.language
    secondary_lang = "en" if current_lang == "pt" else "pt"
    return getattr(value, secondary_lang)


@pass_context
def translate_localizable_string(
    context: dict[str, typing.Any], value: Localizable
) -> str:
    return translate_localizable(value, context["request"].state.language)


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


def highlight_json(value: dict) -> Markup:
    json_str = json.dumps(value, indent=2, ensure_ascii=False)
    return Markup(highlight(json_str, JsonLexer(), HtmlFormatter()))


@pass_context
def get_url_for_asset(
    context: dict[str, typing.Any],
    asset: "record_schemas.RecordAssetReadDetailEmbedded",
    survey_related_record: "record_schemas.SurveyRelatedRecordReadDetail",
) -> str:
    settings: SeisLabDataSettings = context.get("settings")
    return "/".join(
        (
            settings.public_url,
            survey_related_record.survey_mission.project.root_path,
            survey_related_record.survey_mission.relative_path,
            asset.relative_path,
        )
    )
