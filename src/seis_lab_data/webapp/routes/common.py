import dataclasses
import logging
import uuid
from typing import (
    Final,
    Type,
    TypeVar,
)

import pydantic
from jinja2.filters import do_truncate
from starlette.exceptions import HTTPException
from starlette.requests import Request

from ...localization import translate_localizable
from ...schemas import identifiers, surveyrelatedrecords as record_schemas

logger = logging.getLogger(__name__)

UPDATE_BASEMAP_JS_SCRIPT: Final[str] = (
    "window.featureCollection = JSON.parse('{dumped_features}');"
    "document.querySelector('base-map').map.getSource('polygons').setData(featureCollection);"
)


@dataclasses.dataclass
class PaginationInfo:
    current_page: int
    page_size: int
    total_filtered_items: int
    total_unfiltered_items: int
    total_filtered_pages: int
    total_unfiltered_pages: int
    next_page: int | None
    previous_page: int | None
    collection_url: str
    next_page_url: str | None
    previous_page_url: str | None


@pydantic.validate_call
def get_pagination_info(
    current_page: pydantic.NonNegativeInt,
    page_size: pydantic.PositiveInt,
    total_filtered_items: pydantic.NonNegativeInt,
    total_unfiltered_items: pydantic.NonNegativeInt,
    collection_url: str,
) -> PaginationInfo:
    total_filtered_pages = get_page_count(total_filtered_items, page_size)
    total_unfiltered_pages = get_page_count(total_unfiltered_items, page_size)
    next_page = current_page + 1 if current_page < total_filtered_pages else None
    previous_page = current_page - 1 if current_page > 0 else None
    return PaginationInfo(
        current_page=current_page,
        page_size=page_size,
        total_filtered_items=total_filtered_items,
        total_unfiltered_items=total_unfiltered_items,
        total_filtered_pages=total_filtered_pages,
        total_unfiltered_pages=total_unfiltered_pages,
        next_page=next_page,
        previous_page=previous_page,
        collection_url=collection_url,
        next_page_url=f"{collection_url}?page={next_page}" if next_page else None,
        previous_page_url=(
            f"{collection_url}?page={previous_page}" if previous_page else None
        ),
    )


RequestPathRetrievableIdType = TypeVar(
    "RequestPathRetrievableIdType",
    identifiers.ProjectId,
    identifiers.SurveyMissionId,
    identifiers.SurveyRelatedRecordId,
)


def get_id_from_request_path[RequestPathRetrievableIdType](
    request: Request, path_param_name: str, id_type: Type[RequestPathRetrievableIdType]
) -> RequestPathRetrievableIdType:
    try:
        return id_type(uuid.UUID(request.path_params[path_param_name]))
    except ValueError as err:
        raise HTTPException(400, f"Invalid ID format for {id_type.__name__}") from err


def get_page_from_request_params(
    request: Request,
    query_param_name: str = "page",
) -> int:
    try:
        current_page = int(request.query_params.get(query_param_name, 1))
        if current_page < 1:
            raise ValueError
        return current_page
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid page number")


@pydantic.validate_call
def get_page_count(
    total_items: pydantic.NonNegativeInt, page_size: pydantic.PositiveInt
) -> int:
    return (total_items + page_size - 1) // page_size


def build_related_record_compound_name(
    request: Request,
    survey_related_record: record_schemas.SurveyRelatedRecordReadEmbedded
    | record_schemas.SurveyRelatedRecordReadListItem,
) -> str:
    current_language = request.state.language
    current_name = translate_localizable(survey_related_record.name, current_language)
    current_mission_name = do_truncate(
        request.state.templates.env,
        translate_localizable(
            survey_related_record.survey_mission.name, current_language
        ),
        length=15,
        killwords=True,
        leeway=0,
    )
    current_project_name = do_truncate(
        request.state.templates.env,
        translate_localizable(
            survey_related_record.survey_mission.project.name, current_language
        ),
        length=15,
        killwords=True,
        leeway=0,
    )
    return f"{current_name} ({current_mission_name} - {current_project_name}) - {survey_related_record.id}"
