import dataclasses
import datetime as dt
import enum
import json
import logging
import re
import urllib.parse
import uuid
from collections.abc import Mapping
from typing import (
    ClassVar,
    Protocol,
    Self,
)

import shapely

from .. import constants
from ..schemas import identifiers
from ..schemas.filters import TemporalExtentFilterValue

logger = logging.getLogger(__name__)


class ListFilter[ValueType](Protocol):
    internal_name: str
    value: ValueType

    def serialize_to_query_params(self) -> dict[str, str]: ...

    def as_kwargs(self) -> dict[str, ValueType]:
        return {self.internal_name: self.value}


class SimpleListFilter(ListFilter, Protocol):
    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self: ...


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

    def serialize_to_query_params(self) -> dict[str, str]:
        result = {}
        if self.value.begin:
            result["temporalExtentBegin"] = self.value.begin.strftime("%Y-%m-%d")
        if self.value.end:
            result["temporalExtentEnd"] = self.value.end.strftime("%Y-%m-%d")
        return result


@dataclasses.dataclass
class _StatusFilter(SimpleListFilter):
    value: enum.Enum
    internal_name: str = "status"
    public_name: str = "filterStatus"
    status_type: ClassVar[type[enum.Enum]]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        # an absent param, or any value outside the status enum, raises ValueError
        return cls(value=cls.status_type(params.get(cls.public_name)))

    def serialize_to_query_params(self) -> dict[str, str]:
        return {self.public_name: self.value.value}


@dataclasses.dataclass
class ProjectStatusFilter(_StatusFilter):
    status_type = constants.ProjectStatus


@dataclasses.dataclass
class SurveyMissionStatusFilter(_StatusFilter):
    status_type = constants.SurveyMissionStatus


@dataclasses.dataclass
class SurveyRelatedRecordStatusFilter(_StatusFilter):
    status_type = constants.SurveyRelatedRecordStatus


@dataclasses.dataclass
class BoundingBoxFilter(SimpleListFilter):
    """Filter by intersection with a bounding box in EPSG:4326."""

    internal_name = "spatial_intersect"
    value: shapely.Polygon
    switch_name: ClassVar[str] = "filterByMapArea"

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        """Build the filter from the `minLon`, `minLat`, `maxLon` and `maxLat` params.

        Raise `ValueError` unless the `filterByMapArea` param is `True` or
        `"true"` and all four coordinates are numeric.

        Longitudes are shifted by whole turns so that `minLon` lies in
        [-180, 180). A box spanning 360 degrees of longitude or more covers the
        whole longitude range, and a box extending past 180 degrees is clipped
        at 180, as the remainder would require a second polygon. Latitudes are
        clamped to [-90, 90].
        """
        if params.get(cls.switch_name) not in (True, "true"):
            raise ValueError(f"{cls.switch_name!r} is not set")
        try:
            min_lon, min_lat, max_lon, max_lat = (
                float(params[name]) for name in ("minLon", "minLat", "maxLon", "maxLat")
            )
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(
                "Must provide numeric minLon, minLat, maxLon and maxLat"
            ) from err
        if max_lon - min_lon >= 360:
            min_lon, max_lon = -180.0, 180.0
        else:
            shift = 360 * ((min_lon + 180) // 360)
            min_lon, max_lon = min_lon - shift, min(max_lon - shift, 180.0)
        return cls(
            value=shapely.box(
                xmin=min_lon,
                ymin=max(min_lat, -90.0),
                xmax=max_lon,
                ymax=min(max_lat, 90.0),
            )
        )

    def serialize_to_query_params(self) -> dict[str, str]:
        if not self.value.is_valid:
            logger.debug("bbox filter geometry is not valid")
            return {}
        min_lon, min_lat, max_lon, max_lat = self.value.bounds
        return {
            self.switch_name: "true",
            "minLon": str(min_lon),
            "minLat": str(min_lat),
            "maxLon": str(max_lon),
            "maxLat": str(max_lat),
        }


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

    def serialize_to_query_params(self) -> dict[str, str]:
        return (
            {self.public_name: self.value}
            if all((self.value, self.public_name))
            else {}
        )


@dataclasses.dataclass
class NameFilter(_StringFilter):
    internal_name: str = "name_filter"
    public_name: str = "search"


@dataclasses.dataclass
class DatasetCategoryFilter(SimpleListFilter):
    value: identifiers.DatasetCategoryId | None
    internal_name: str = "dataset_category_id"
    public_name: str = "filterDatasetCategory"

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        if (raw_value := params.get(cls.public_name)) is not None:
            parsed = identifiers.DatasetCategoryId(uuid.UUID(raw_value))
        else:
            parsed = None
        logger.debug(f"inside DatasetCategoryFilter.from_params() - {locals()=}")
        return cls(value=parsed)

    def serialize_to_query_params(self) -> dict[str, str]:
        return {self.public_name: str(self.value)} if self.value else {}


@dataclasses.dataclass
class WorkflowStageFilter(SimpleListFilter):
    value: identifiers.WorkflowStageId | None
    internal_name: str = "workflow_stage_id"
    public_name: str = "filterWorkflowStage"

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        if (raw_value := params.get(cls.public_name)) is not None:
            parsed = identifiers.WorkflowStageId(uuid.UUID(raw_value))
        else:
            parsed = None
        return cls(value=parsed)

    def serialize_to_query_params(self) -> dict[str, str]:
        return {self.public_name: str(self.value)} if self.value else {}


@dataclasses.dataclass
class PathFragmentFilter(_StringFilter):
    internal_name: str = "asset_path_fragment_filter"
    public_name: str = "assetPathFragment"


@dataclasses.dataclass
class MediaTypeFilter(_StringFilter):
    internal_name: str = "asset_media_type_filter"
    public_name: str = "filterMediaType"


@dataclasses.dataclass
class ProjectIdFilter(_StringFilter):
    internal_name: str = "project_id"
    public_name: str = "projectId"

    def serialize_to_query_params(self) -> dict[str, str]:
        return {}


@dataclasses.dataclass
class SurveyMissionIdFilter(_StringFilter):
    internal_name: str = "survey_mission_id"
    public_name: str = "surveyMissionId"

    def serialize_to_query_params(self) -> dict[str, str]:
        return {}


_compound_name_id_regex = re.compile(r" (?P<id>\w{8}-\w{4}-\w{4}-\w{4}-\w{12})$")


@dataclasses.dataclass
class ProjectCompoundNameFilter(_StringFilter):
    """Filter by a project, given as its compound name: a name ending with the id.

    The filter serializes to the compound name rather than to the bare id.
    """

    internal_name: str = "project_id"
    public_name: str = "filterProject"
    value: identifiers.ProjectId | None
    compound_name: str = ""

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        raw_value = params.get(cls.public_name, "")
        if (re_obj := _compound_name_id_regex.search(raw_value)) is not None:
            return cls(
                value=identifiers.ProjectId(uuid.UUID(re_obj.groupdict()["id"])),
                compound_name=raw_value,
            )
        else:
            raise ValueError(f"Cannot find a valid compound name in {raw_value!r}")

    def serialize_to_query_params(self) -> dict[str, str]:
        return {self.public_name: self.compound_name} if self.compound_name else {}


@dataclasses.dataclass
class SurveyMissionCompoundNameFilter(_StringFilter):
    """Filter by a survey mission, given as its compound name: a name ending with the id.

    The filter serializes to the compound name rather than to the bare id.
    """

    internal_name: str = "survey_mission_id"
    public_name: str = "filterMission"
    value: identifiers.SurveyMissionId | None
    compound_name: str = ""

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        raw_value = params.get(cls.public_name, "")
        if (re_obj := _compound_name_id_regex.search(raw_value)) is not None:
            return cls(
                value=identifiers.SurveyMissionId(uuid.UUID(re_obj.groupdict()["id"])),
                compound_name=raw_value,
            )
        else:
            raise ValueError(f"Cannot find a valid compound name in {raw_value!r}")

    def serialize_to_query_params(self) -> dict[str, str]:
        return {self.public_name: self.compound_name} if self.compound_name else {}


class ItemListFilters(Protocol):
    filters: dict[str, ListFilter]

    @property
    def spatial_intersect_filter(self) -> BoundingBoxFilter | None:
        return self.filters.get("spatial_intersect")

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self: ...

    @classmethod
    def from_json(cls, raw_params: str):
        params = json.loads(raw_params)
        return cls.from_params(params)

    def get_text_search_filter(self) -> str:
        return f_.value if (f_ := self.filters.get(NameFilter.internal_name)) else ""

    def serialize_to_query_string(self) -> str:
        query_params = {}
        for filter_ in self.filters.values():
            query_params.update(filter_.serialize_to_query_params())
        return f"?{urllib.parse.urlencode(query_params)}" if query_params else ""

    def as_kwargs(self) -> dict:
        return {
            f.internal_name: f.value for f in self.filters.values() if f.value != ""
        }


@dataclasses.dataclass
class DatasetCategoryListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        filters: dict[str, SimpleListFilter] = {}
        for simple_type in (NameFilter,):
            try:
                filter_: SimpleListFilter = simple_type.from_params(params)
                filters[filter_.internal_name] = filter_
            except ValueError as err:
                logger.info(str(err))
        return cls(filters=filters)


@dataclasses.dataclass
class WorkflowStageListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        filters: dict[str, SimpleListFilter] = {}
        for simple_type in (NameFilter,):
            try:
                filter_: SimpleListFilter = simple_type.from_params(params)
                filters[filter_.internal_name] = filter_
            except ValueError as err:
                logger.info(str(err))
        return cls(filters=filters)


@dataclasses.dataclass
class AssetDiscoveryConfigurationListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        filters: dict[str, SimpleListFilter] = {}
        try:
            name_filter = NameFilter.from_params(params)
            filters[name_filter.internal_name] = name_filter
        except ValueError as err:
            logger.info(str(err))
        return cls(filters)


@dataclasses.dataclass
class ProjectListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        filters: dict[str, SimpleListFilter] = {}
        for simple_type in (
            BoundingBoxFilter,
            ProjectStatusFilter,
            TemporalExtentFilter,
            NameFilter,
        ):
            try:
                filter_: SimpleListFilter = simple_type.from_params(params)
                filters[filter_.internal_name] = filter_
            except ValueError as err:
                logger.info(str(err))
        return cls(filters=filters)


@dataclasses.dataclass
class SurveyMissionListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        filters: dict[str, SimpleListFilter] = {}
        for simple_type in (
            BoundingBoxFilter,
            TemporalExtentFilter,
            NameFilter,
            SurveyMissionStatusFilter,
            ProjectIdFilter,
            ProjectCompoundNameFilter,
        ):
            try:
                filter_: SimpleListFilter = simple_type.from_params(params)
                filters[filter_.internal_name] = filter_
            except ValueError as err:
                logger.info(str(err))
        return cls(filters=filters)


@dataclasses.dataclass
class SurveyRelatedRecordListFilters(ItemListFilters):
    filters: dict[str, ListFilter]

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> Self:
        filters: dict[str, SimpleListFilter] = {}
        for simple_type in (
            BoundingBoxFilter,
            TemporalExtentFilter,
            NameFilter,
            SurveyRelatedRecordStatusFilter,
            DatasetCategoryFilter,
            MediaTypeFilter,
            WorkflowStageFilter,
            SurveyMissionIdFilter,
            SurveyMissionCompoundNameFilter,
            ProjectCompoundNameFilter,
            PathFragmentFilter,
        ):
            try:
                filter_: SimpleListFilter = simple_type.from_params(params)
                filters[filter_.internal_name] = filter_
            except ValueError as err:
                logger.info(str(err))
        return cls(filters=filters)
