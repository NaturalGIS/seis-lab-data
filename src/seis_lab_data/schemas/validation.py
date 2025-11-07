import datetime as dt
from typing import (
    Annotated,
    cast,
)

import shapely
import pydantic
from geoalchemy2 import WKBElement

from .. import constants
from . import common


def validate_polygon_geometry(value: shapely.Polygon) -> shapely.Polygon:
    if not value.is_valid:
        raise ValueError("Polygon geometry is invalid")
    return value


def ensure_root_path_exists(value: str) -> str:
    return value


def ensure_relative_path_exists(value: str) -> str:
    # TODO: this validation needs access to the parent project's root_path
    return value


class LocalizableValidName(pydantic.BaseModel):
    en: Annotated[
        str,
        pydantic.Field(
            min_length=constants.NAME_MIN_LENGTH, max_length=constants.NAME_MAX_LENGTH
        ),
    ]
    pt: Annotated[
        str,
        pydantic.Field(
            min_length=constants.NAME_MIN_LENGTH,
            max_length=constants.NAME_MAX_LENGTH,
        ),
    ]


class LocalizableValidDescription(pydantic.BaseModel):
    en: Annotated[
        str,
        pydantic.Field(
            min_length=constants.DESCRIPTION_MIN_LENGTH,
            max_length=constants.DESCRIPTION_MAX_LENGTH,
        ),
    ]
    pt: Annotated[
        str,
        pydantic.Field(
            min_length=constants.DESCRIPTION_MIN_LENGTH,
            max_length=constants.DESCRIPTION_MAX_LENGTH,
        ),
    ]


class ValidLinkSchema(pydantic.BaseModel):
    url: pydantic.AnyHttpUrl
    media_type: str
    relation: str
    # NOTE: the below field is named 'link_description' intentionally - do not change
    #
    # The reason is that we have some smarts to perform validation on forms
    # generated with wtforms and this means the names of form fields must be the
    # same as pydantic model fields. It just so happens that links are modeled
    # in a wtforms formfield, which also has a 'description' property and this
    # naming was chosen to avoid clashes
    link_description: LocalizableValidDescription


def parse_possibly_empty_wkbelement_polygon_into_valid_geometry(
    value: WKBElement | None,
) -> shapely.Polygon:
    if value is None:
        raise ValueError("value is None")
    try:
        geom = shapely.from_wkb(value.data)
    except shapely.GEOSException as err:
        raise ValueError(f"Could not parse {value} as WKB") from err
    else:
        if not geom.is_valid:
            raise ValueError("Geometry is not valid")
        if geom.geom_type != "Polygon":
            raise ValueError("Geometry is not a Polygon")
        if geom.area == 0:
            raise ValueError("Polygon has zero area")
    return cast(shapely.Polygon, geom)


class ValidProject(pydantic.BaseModel):
    id: common.ProjectId
    name: LocalizableValidName
    description: LocalizableValidDescription
    status: constants.ProjectStatus
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None
    owner: common.UserId
    root_path: Annotated[str, pydantic.PlainValidator(ensure_root_path_exists)]
    links: list[ValidLinkSchema] = []
    bbox_4326: Annotated[
        shapely.Polygon,
        pydantic.PlainValidator(
            parse_possibly_empty_wkbelement_polygon_into_valid_geometry
        ),
    ]


class ValidSurveyMission(pydantic.BaseModel):
    id: common.SurveyMissionId
    name: LocalizableValidName
    description: LocalizableValidDescription
    status: constants.SurveyMissionStatus
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None
    owner: common.UserId
    relative_path: Annotated[str, pydantic.PlainValidator(ensure_relative_path_exists)]
    links: list[ValidLinkSchema] = []
    bbox_4326: Annotated[
        shapely.Polygon,
        pydantic.PlainValidator(
            parse_possibly_empty_wkbelement_polygon_into_valid_geometry
        ),
    ]


class ValidSurveyRelatedRecord(pydantic.BaseModel):
    id: common.SurveyRelatedRecordId
    name: LocalizableValidName
    dataset_category_id: common.DatasetCategoryId
    domain_type_id: common.DomainTypeId
    workflow_stage_id: common.WorkflowStageId
    description: LocalizableValidDescription
    status: constants.SurveyMissionStatus
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None
    owner: common.UserId
    relative_path: Annotated[str, pydantic.PlainValidator(ensure_relative_path_exists)]
    links: list[ValidLinkSchema] = []
    bbox_4326: Annotated[
        shapely.Polygon,
        pydantic.PlainValidator(
            parse_possibly_empty_wkbelement_polygon_into_valid_geometry
        ),
    ]
