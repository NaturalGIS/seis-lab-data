import dataclasses
import json
import logging
from typing import (
    Mapping,
    Protocol,
)

from typing_extensions import Self

import shapely

logger = logging.getLogger(__name__)


class ListFilter[ValueType](Protocol):
    internal_name: str
    value: ValueType

    def serialize_to_query_string(self) -> str: ...

    def as_kwargs(self) -> dict[str, ValueType]:
        return {self.internal_name: self.value}


class SimpleListFilter(ListFilter, Protocol):
    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self: ...


class LanguageDependantListFilter(ListFilter, Protocol):
    @classmethod
    def from_params(cls, params: Mapping[str, str], current_language: str) -> Self: ...


@dataclasses.dataclass
class BoundingBoxFilter(SimpleListFilter):
    internal_name = "spatial_intersect"
    value: shapely.Polygon

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        try:
            raw_min_lon = params["minLon"]
            raw_min_lat = params["minLat"]
            raw_max_lon = params["maxLon"]
            raw_max_lat = params["maxLat"]
        except KeyError as err:
            raise ValueError(
                "Must provide all of minLon, minLat and maxLon and maxLat"
            ) from err
        try:
            return cls(
                value=shapely.box(
                    xmin=float(raw_min_lon),
                    ymin=float(raw_min_lat),
                    xmax=float(raw_max_lon),
                    ymax=float(raw_max_lat),
                )
            )
        except TypeError as err:
            msg = "Could not parse bounding box"
            logger.exception(msg)
            raise ValueError(msg) from err

    def serialize_to_query_string(self) -> str:
        min_lon, min_lat, max_lon, max_lat = self.value.bounds
        return "&".join(
            (
                f"minLon={min_lon}",
                f"minLat={min_lat}",
                f"maxLon={max_lon}",
                f"maxLat={max_lat}",
            )
        )


@dataclasses.dataclass
class _StringFilter(SimpleListFilter):
    value: str
    internal_name: str = ""
    public_name: str = ""

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        try:
            return cls(value=params[cls.public_name])
        except KeyError as err:
            raise ValueError(f"Cannot find {cls.public_name!r} in params") from err

    def serialize_to_query_string(self) -> str:
        return f"{self.public_name}={self.value}" if self.value else ""


@dataclasses.dataclass
class EnNameFilter(_StringFilter):
    internal_name: str = "en_name_filter"
    public_name: str = "en_name"


@dataclasses.dataclass
class PtNameFilter(_StringFilter):
    internal_name: str = "pt_name_filter"
    public_name: str = "pt_name"


@dataclasses.dataclass
class SearchNameFilter(LanguageDependantListFilter):
    internal_name: str
    public_name: str
    value: str

    @classmethod
    def from_params(cls, params: Mapping[str, str], current_language: str) -> Self:
        _name = "search"
        try:
            return cls(
                internal_name=f"{current_language}_name_filter",
                public_name=f"{current_language}_name",
                value=params[_name],
            )
        except KeyError as err:
            raise ValueError(f"Cannot find {_name!r} in params") from err

    def serialize_to_query_string(self) -> str:
        return f"{self.public_name}={self.value}" if self.value else ""


class ItemListFilters(Protocol):
    filters: dict[str, ListFilter]

    @property
    def spatial_intersect_filter(self) -> BoundingBoxFilter | None:
        return self.filters.get("spatial_intersect")

    @classmethod
    def from_params(cls, params: Mapping[str, str], current_language: str) -> Self: ...

    @classmethod
    def from_json(cls, raw_params: str, current_language: str):
        params = json.loads(raw_params)
        return cls.from_params(params, current_language)

    def get_text_search_filter(self, current_language: str) -> str:
        filter_internal_name = f"{current_language}_name_filter"
        return self.filters.get(filter_internal_name, "").value

    def serialize_to_query_string(self) -> str:
        result = ""
        for filter_ in self.filters.values():
            if (serialized := filter_.serialize_to_query_string()) != "":
                result = f"{result}&{serialized}" if result != "" else serialized
        return f"?{result}" if result != "" else ""

    def as_kwargs(self) -> dict:
        return {f.internal_name: f.value for f in self.filters.values()}


@dataclasses.dataclass
class ProjectListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str], current_language: str) -> Self:
        filters: dict[str, SimpleListFilter | LanguageDependantListFilter] = {}
        for simple_type in (
            BoundingBoxFilter,
            EnNameFilter,
            PtNameFilter,
        ):
            try:
                filter_: SimpleListFilter = simple_type.from_params(params)
                filters[filter_.internal_name] = filter_
            except ValueError as err:
                logger.info(str(err))
        try:
            filter_: LanguageDependantListFilter = SearchNameFilter.from_params(
                params, current_language
            )
            filters[filter_.internal_name] = filter_
        except ValueError as err:
            logger.info(str(err))
        return cls(filters=filters)


@dataclasses.dataclass
class SurveyMissionListFilters(ProjectListFilters): ...
