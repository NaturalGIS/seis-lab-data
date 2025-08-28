import uuid

import pydantic

from .common import (
    LinkSchema,
    AtLeastEnglishLocalizableString,
)


class MarineCampaignCreate(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: AtLeastEnglishLocalizableString
    root_path: str
    links: list[LinkSchema] = []


class MarineCampaignUpdate(pydantic.BaseModel):
    owner: str | None = None
    name: AtLeastEnglishLocalizableString | None = None
    root_path: str | None = None
    links: list[LinkSchema] | None = None


class MarineCampaignReadListItem(pydantic.BaseModel):
    id: uuid.UUID
    slug: str


class MarineCampaignReadDetail(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: AtLeastEnglishLocalizableString
    root_path: str
    slug: str
    links: list[LinkSchema] = []
