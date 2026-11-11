"""Custom jinja filters."""

import logging
import typing

import shapely
from jinja2 import pass_context

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
