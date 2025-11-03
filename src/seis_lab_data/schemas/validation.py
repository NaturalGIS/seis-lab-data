import datetime as dt
from typing import Annotated

import shapely
import pydantic

from .. import constants
from . import common


def validate_polygon_geometry(value: shapely.Polygon) -> shapely.Polygon:
    if not value.is_valid:
        raise ValueError("Polygon geometry is invalid")
    return value


def ensure_root_path_exists(value: str) -> str:
    return value


class ValidationError(pydantic.BaseModel):
    name: str
    message: str


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


class ValidProject(pydantic.BaseModel):
    id: common.ProjectId
    name: LocalizableValidName
    status: constants.ProjectStatus
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None
    owner: common.UserId
    root_path: Annotated[str, pydantic.PlainValidator(ensure_root_path_exists)]
    links: list[ValidLinkSchema] = []
    bbox_4326: Annotated[
        shapely.Polygon, pydantic.PlainValidator(validate_polygon_geometry)
    ]
