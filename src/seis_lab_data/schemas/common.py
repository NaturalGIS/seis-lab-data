from typing import (
    Annotated,
    NewType,
)
import uuid

import babel
import pydantic
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
)
from pydantic_core import PydanticCustomError

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


def has_valid_locales(value: dict[str, str]):
    try:
        for key in value.keys():
            babel.Locale.parse(key)
    except babel.UnknownLocaleError as exc:
        raise ValueError(exc) from exc
    return value


def has_english_locale(value: dict[str, str], info: pydantic.ValidationInfo):
    try:
        result = value["en"] != ""
    except KeyError:
        raise PydanticCustomError(
            "missing_english_locale",
            "{field} missing english locale",
            {"field": info.field_name, "language": "en"},
        )
    if not result:
        # raise ValueError("Missing english locale value")
        raise PydanticCustomError(
            "missing_english_locale_value",
            "{field} missing english locale value",
            {"field": info.field_name, "language": "en"},
        )
    return value


def has_portuguese_locale(value: dict[str, str]):
    try:
        result = value["pt"] != ""
    except KeyError as exc:
        raise ValueError("Missing portuguese locale") from exc
    if not result:
        raise ValueError("Missing portuguese locale value")
    return value


NameString = Annotated[
    str,
    Field(max_length=constants.NAME_MAX_LENGTH),
]
_LocalizableName = Annotated[dict[str, NameString], AfterValidator(has_valid_locales)]
AtLeastEnglishName = Annotated[_LocalizableName, AfterValidator(has_english_locale)]

PublishableNameString = Annotated[
    str,
    Field(min_length=constants.NAME_MIN_LENGTH, max_length=constants.NAME_MAX_LENGTH),
]
_LocalizablePublishableName = Annotated[
    dict[str, PublishableNameString], AfterValidator(has_valid_locales)
]
_PublishableEnName = Annotated[
    _LocalizablePublishableName, AfterValidator(has_english_locale)
]
PublishableName = Annotated[_PublishableEnName, AfterValidator(has_portuguese_locale)]


DescriptionString = Annotated[str, Field(max_length=constants.DESCRIPTION_MAX_LENGTH)]
LocalizableDescription = Annotated[
    dict[str, DescriptionString], AfterValidator(has_valid_locales)
]
AtLeastEnglishDescription = Annotated[
    LocalizableDescription, AfterValidator(has_english_locale)
]

PublishableDescriptionString = Annotated[
    str,
    Field(
        min_length=constants.DESCRIPTION_MIN_LENGTH,
        max_length=constants.DESCRIPTION_MAX_LENGTH,
    ),
]
_LocalizablePublishableDescription = Annotated[
    dict[str, PublishableDescriptionString], AfterValidator(has_valid_locales)
]
_PublishableEnDescription = Annotated[
    _LocalizablePublishableDescription, AfterValidator(has_english_locale)
]
PublishableDescription = Annotated[
    _PublishableEnDescription, AfterValidator(has_portuguese_locale)
]


LocalizableString = Annotated[dict[str, str], AfterValidator(has_valid_locales)]
AtLeastEnglishLocalizableString = Annotated[
    LocalizableString, AfterValidator(has_english_locale)
]


class LinkSchema(BaseModel):
    url: str
    media_type: str
    relation: str
    description: AtLeastEnglishLocalizableString
