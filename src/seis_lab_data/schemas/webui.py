import dataclasses
import typing

import pydantic
from starlette_babel import LazyString
from starlette.datastructures import URL

from .projects import ProjectReadDetail
from .surveymissions import (
    SurveyMissionReadDetail,
    SurveyMissionReadListItem,
)
from .surveyrelatedrecords import (
    SurveyRelatedRecordReadDetail,
    SurveyRelatedRecordReadListItem,
    RecordAssetReadDetail,
    RecordAssetReadListItem,
)


class BreadcrumbItem(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    name: LazyString | str
    url: URL | str | None = None


@dataclasses.dataclass(frozen=True)
class ItemSelectorInfo:
    feedback: str
    item_details: str
    item_name: str
    breadcrumbs: str


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


@dataclasses.dataclass(frozen=True)
class UserPermissionDetails:
    can_create_children: bool
    can_update: bool
    can_delete: bool


ItemWithDetails = typing.TypeVar(
    "ItemWithDetails",
    ProjectReadDetail,
    SurveyMissionReadDetail,
    SurveyRelatedRecordReadDetail,
    RecordAssetReadDetail,
)

ItemChildSummary = typing.TypeVar(
    "ItemChildSummary",
    SurveyMissionReadListItem,
    SurveyRelatedRecordReadListItem,
    RecordAssetReadListItem,
)


@dataclasses.dataclass(frozen=True)
class ItemDetails(typing.Generic[ItemWithDetails, ItemChildSummary]):
    item: ItemWithDetails
    children: list[ItemChildSummary]
    pagination: PaginationInfo
    permissions: UserPermissionDetails
    breadcrumbs: list[BreadcrumbItem]


@dataclasses.dataclass(frozen=True)
class ProjectDetails(ItemDetails[ProjectReadDetail, SurveyMissionReadListItem]):
    """Details for a project, including its survey missions, permissions and pagination."""


@dataclasses.dataclass(frozen=True)
class SurveyMissionDetails(
    ItemDetails[SurveyMissionReadDetail, SurveyRelatedRecordReadDetail]
):
    """Details for a survey mission, including its records, permissions and pagination."""
