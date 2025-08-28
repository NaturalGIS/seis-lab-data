import uuid

import pydantic

from .common import (
    AtLeastEnglishLocalizableString,
)


class DatasetCategoryCreate(pydantic.BaseModel):
    id: uuid.UUID
    name: AtLeastEnglishLocalizableString


class DatasetCategoryRead(pydantic.BaseModel):
    id: uuid.UUID
    name: AtLeastEnglishLocalizableString


class DomainTypeCreate(pydantic.BaseModel):
    id: uuid.UUID
    name: AtLeastEnglishLocalizableString


class DomainTypeRead(pydantic.BaseModel):
    id: uuid.UUID
    name: AtLeastEnglishLocalizableString


class WorkflowStageCreate(pydantic.BaseModel):
    id: uuid.UUID
    name: AtLeastEnglishLocalizableString


class WorkflowStageRead(pydantic.BaseModel):
    id: uuid.UUID
    name: AtLeastEnglishLocalizableString
