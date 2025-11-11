import datetime as dt
import logging
import typing

import shapely

logger = logging.getLogger(__name__)


class GeoJsonPolygonGeometry(typing.TypedDict):
    type: typing.Literal["Polygon"]
    coordinates: typing.Sequence[typing.Sequence[float]]


class GeoJsonPolygonFeature(typing.TypedDict):
    id: str | int
    type: typing.Literal["Feature"]
    geometry: GeoJsonPolygonGeometry
    properties: dict


class GeoJsonFeatureCollection(typing.TypedDict):
    type: str
    features: list[GeoJsonPolygonFeature]


class GeospatialItemWithBoundingBox(typing.Protocol):
    id: str
    bbox_4326: shapely.Polygon
    temporal_extent_begin: dt.date | None
    temporal_extent_end: dt.date | None

    def model_dump(self, exclude: set[str], **kwargs) -> dict: ...


def to_feature_collection(
    items: list[GeospatialItemWithBoundingBox],
) -> GeoJsonFeatureCollection:
    result = GeoJsonFeatureCollection(type="FeatureCollection", features=[])
    for item in items:
        feature = GeoJsonPolygonFeature(
            id=str(item.id),
            type="Feature",
            geometry=(
                GeoJsonPolygonGeometry(**(item.bbox_4326.__geo_interface__))
                if item.bbox_4326
                else None
            ),
            properties={
                **item.model_dump(
                    exclude={
                        "id",
                        "bbox_4326",
                    }
                ),
            },
        )
        result["features"].append(feature)
    return result
