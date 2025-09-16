from typing import (
    Annotated,
    NewType,
    Protocol,
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
