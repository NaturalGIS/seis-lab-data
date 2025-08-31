import uuid

import pydantic

from ..constants import MarineCampaignStatus
from .common import (
    LinkSchema,
    AtLeastEnglishLocalizableString,
    AtLeastEnglishDescription,
)


class MarineCampaignCreate(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: AtLeastEnglishLocalizableString
    description: AtLeastEnglishDescription
    root_path: str
    links: list[LinkSchema] = []


class MarineCampaignUpdate(pydantic.BaseModel):
    owner: str | None = None
    name: AtLeastEnglishLocalizableString | None = None
    description: AtLeastEnglishDescription
    root_path: str | None = None
    links: list[LinkSchema] | None = None


class MarineCampaignReadListItem(pydantic.BaseModel):
    id: uuid.UUID
    slug: str
    name: AtLeastEnglishLocalizableString
    description: AtLeastEnglishDescription
    status: MarineCampaignStatus
    is_valid: bool


class MarineCampaignReadDetail(MarineCampaignReadListItem):
    owner: str
    root_path: str
    links: list[LinkSchema] = []
