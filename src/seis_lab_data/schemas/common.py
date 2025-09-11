from typing import (
    Annotated,
    NewType,
    TypedDict,
)
import uuid

import pydantic

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


class Localizable(TypedDict):
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


class LocalizableDraftLinkDescription(pydantic.BaseModel):
    en: Annotated[str, pydantic.Field(max_length=constants.DESCRIPTION_MAX_LENGTH)]
    pt: (
        Annotated[str, pydantic.Field(max_length=constants.DESCRIPTION_MAX_LENGTH)]
        | None
    ) = None


class LinkSchema(pydantic.BaseModel):
    url: str
    media_type: str
    relation: str
    description: LocalizableDraftLinkDescription
