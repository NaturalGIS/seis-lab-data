import dataclasses
import datetime as dt
import json
import logging
from typing import (
    Mapping,
    Protocol,
)

from typing_extensions import Self

import shapely

from ..schemas import TemporalExtentFilterValue

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
class TemporalExtentFilter(SimpleListFilter):
    internal_name = "temporal_extent"
    value: TemporalExtentFilterValue

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        raw_begin = params.get("temporalExtentBegin") or None
        raw_end = params.get("temporalExtentEnd") or None
        if not any((raw_begin, raw_end)):
            raise ValueError("Could not find temporal extent parameters")
        value = TemporalExtentFilterValue(
            begin=(
                dt.datetime.strptime(raw_begin, "%Y-%m-%d").date()
                if raw_begin
                else raw_begin
            ),
            end=(
                dt.datetime.strptime(raw_end, "%Y-%m-%d").date() if raw_end else raw_end
            ),
        )
        return cls(value=value)

    def serialize_to_query_string(self) -> str:
        result = ""
        if self.value.begin:
            result = f"temporalExtentBegin={self.value.begin.strftime('%Y-%m-%d')}"
        if self.value.end:
            result += f"&temporalExtentEnd={self.value.end.strftime('%Y-%m-%d')}"
        return result[1:] if result.startswith("&") else result


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
        if not self.value.is_valid:
            logger.debug("bbox filter geometry is not valid")
            return ""
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
        return (
            f"{self.public_name}={self.value}"
            if all((self.value, self.public_name))
            else ""
        )


@dataclasses.dataclass
class EnNameFilter(_StringFilter):
    internal_name: str = "en_name_filter"
    public_name: str = "en_name"


@dataclasses.dataclass
class PtNameFilter(_StringFilter):
    internal_name: str = "pt_name_filter"
    public_name: str = "pt_name"


@dataclasses.dataclass
class DatasetCategoryFilter(_StringFilter):
    internal_name: str = "dataset_category_filter"
    public_name: str = "dataset_category"


@dataclasses.dataclass
class DomainTypeFilter(_StringFilter):
    internal_name: str = "domain_type_filter"
    public_name: str = "domain_type"


@dataclasses.dataclass
class WorkflowStageFilter(_StringFilter):
    internal_name: str = "workflow_stage_filter"
    public_name: str = "workflow_stage"


@dataclasses.dataclass
class ProjectIdFilter(_StringFilter):
    internal_name: str = "project_id"
    public_name: str = "projectId"

    def serialize_to_query_string(self) -> str:
        return ""


@dataclasses.dataclass
class SurveyMissionIdFilter(_StringFilter):
    internal_name: str = "survey_mission_id"
    public_name: str = "surveyMissionId"

    def serialize_to_query_string(self) -> str:
        return ""


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
        return f_.value if (f_ := self.filters.get(filter_internal_name)) else ""

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
            TemporalExtentFilter,
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
class SurveyMissionListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str], current_language: str) -> Self:
        filters: dict[str, SimpleListFilter | LanguageDependantListFilter] = {}
        for simple_type in (
            BoundingBoxFilter,
            TemporalExtentFilter,
            EnNameFilter,
            PtNameFilter,
            DatasetCategoryFilter,
            DomainTypeFilter,
            WorkflowStageFilter,
            ProjectIdFilter,
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
class SurveyRelatedRecordListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str], current_language: str) -> Self:
        filters: dict[str, SimpleListFilter | LanguageDependantListFilter] = {}
        for simple_type in (
            BoundingBoxFilter,
            TemporalExtentFilter,
            EnNameFilter,
            PtNameFilter,
            DatasetCategoryFilter,
            DomainTypeFilter,
            WorkflowStageFilter,
            SurveyMissionIdFilter,
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
