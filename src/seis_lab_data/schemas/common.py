from typing import (
    Annotated,
    NewType,
)
import uuid

import babel
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
)

from .. import constants

DatasetCategoryId = NewType("DatasetCategoryId", uuid.UUID)
DomainTypeId = NewType("DomainTypeId", uuid.UUID)
RecordAssetId = NewType("RecordAssetId", uuid.UUID)
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


def has_english_locale(value: dict[str, str]):
    try:
        result = value["en"] != ""
    except KeyError as exc:
        raise ValueError("Missing english locale") from exc
    if not result:
        raise ValueError("Missing english locale value")
    return value


NameString = Annotated[
    str,
    Field(min_length=constants.NAME_MIN_LENGTH, max_length=constants.NAME_MAX_LENGTH),
]
LocalizableName = Annotated[dict[str, NameString], AfterValidator(has_valid_locales)]
AtLeastEnglishName = Annotated[LocalizableName, AfterValidator(has_english_locale)]


DescriptionString = Annotated[str, Field(max_length=constants.DESCRIPTION_MAX_LENGTH)]
LocalizableDescription = Annotated[
    dict[str, DescriptionString], AfterValidator(has_valid_locales)
]
AtLeastEnglishDescription = Annotated[
    LocalizableDescription, AfterValidator(has_english_locale)
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
