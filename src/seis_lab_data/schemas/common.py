from typing import (
    Annotated,
    cast,
    NewType,
    Protocol,
)
import uuid

import pydantic
import shapely
from geoalchemy2 import WKBElement

from .. import constants

DatasetCategoryId = NewType("DatasetCategoryId", uuid.UUID)
DomainTypeId = NewType("DomainTypeId", uuid.UUID)
RecordAssetId = NewType("RecordAssetId", uuid.UUID)
RequestId = NewType("RequestId", uuid.UUID)
SurveyRelatedRecordId = NewType("SurveyRelatedRecordId", uuid.UUID)
SurveyMissionId = NewType("SurveyMissionId", uuid.UUID)
ProjectId = NewType("ProjectId", uuid.UUID)
UserId = NewType("UserId", str)
WorkflowStageId = NewType("WorkflowStageId", uuid.UUID)


class Localizable(Protocol):
    en: str | None
    pt: str | None


class LocalizableDraftName(pydantic.BaseModel):
    en: Annotated[
        str, pydantic.Field(min_length=1, max_length=constants.NAME_MAX_LENGTH)
    ]
    pt: Annotated[str, pydantic.Field(max_length=constants.NAME_MAX_LENGTH)] | None = (
        None
    )


class LocalizableDraftDescription(pydantic.BaseModel):
    en: (
        Annotated[str, pydantic.Field(max_length=constants.DESCRIPTION_MAX_LENGTH)]
        | None
    ) = None
    pt: (
        Annotated[str, pydantic.Field(max_length=constants.DESCRIPTION_MAX_LENGTH)]
        | None
    ) = None


class LinkSchema(pydantic.BaseModel):
    url: pydantic.AnyHttpUrl
    media_type: str
    relation: str
    # NOTE: the below field is named 'link_description' intentionally - do not change
    #
    # The reason is that we have some smarts to perform validation on forms
    # generated with wtforms and this means the names of form fields must be the
    # same as pydantic model fields. It just so happens that links are modelled
    # in a wtforms formfield, which also has a 'description' property and this
    # naming was chosen to avoid clashes
    link_description: LocalizableDraftDescription

    @pydantic.field_serializer("url")
    def serialize_url(
        self, url: pydantic.AnyHttpUrl, _info: pydantic.FieldSerializationInfo
    ) -> str:
        return str(url)


def parse_wkt_polygon_into_geom(value: str) -> shapely.Polygon:
    try:
        geom = shapely.from_wkt(value)
    except shapely.GEOSException as err:
        raise ValueError(f"Could not parse {value} as WKT") from err
    else:
        if not geom.is_valid:
            raise ValueError("Geometry is not valid")
        if geom.geom_type != "Polygon":
            raise ValueError("Geometry is not a Polygon")
        if geom.area == 0:
            raise ValueError("Polygon has zero area")
    return cast(shapely.Polygon, geom)


def parse_wkt_into_possibly_invalid_polygon(value: str) -> shapely.Geometry:
    try:
        geom = shapely.from_wkt(value)
    except shapely.GEOSException as err:
        raise ValueError(f"Could not parse {value} as WKT") from err
    if geom.geom_type != "Polygon":
        raise ValueError("Geometry is not a Polygon")
    return geom


def parse_wkbelement_polygon_into_geom(value: WKBElement) -> shapely.Polygon:
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


def serialize_geom_to_wkt(value: shapely.Geometry) -> str:
    return shapely.to_wkt(value)


def serialize_polygon_to_bounds(
    value: shapely.Polygon,
) -> tuple[float, float, float, float]:
    return value.bounds


# suitable for putting values into the DB
# parses a WKT string into a shapely Polygon, serializes back to WKT string
Polygon = Annotated[
    shapely.Polygon,
    pydantic.PlainValidator(parse_wkt_polygon_into_geom),
    pydantic.PlainSerializer(serialize_geom_to_wkt),
]

PossiblyInvalidPolygon = Annotated[
    shapely.Polygon,
    pydantic.PlainValidator(parse_wkt_into_possibly_invalid_polygon),
    pydantic.PlainSerializer(serialize_geom_to_wkt),
]

# suitable for outputting values from the API
# parses a WKBElement into a shapely Polygon, serializes to a min_lon, min_lat, max_lon, max_lat tuple
PolygonOut = Annotated[
    shapely.Polygon,
    pydantic.PlainValidator(parse_wkbelement_polygon_into_geom),
    pydantic.PlainSerializer(serialize_polygon_to_bounds),
]
