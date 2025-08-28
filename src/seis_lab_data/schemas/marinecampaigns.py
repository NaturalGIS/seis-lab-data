import uuid

import pydantic
from slugify import slugify

from .common import (
    LinkSchema,
    LocalizableString,
)


class MarineCampaignCreate(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: LocalizableString
    links: list[LinkSchema] = []

    @pydantic.computed_field
    @property
    def slug(self) -> str:
        return slugify(self.name.get("en", ""))


class MarineCampaignReadListItem(pydantic.BaseModel):
    id: uuid.UUID
    slug: str


class MarineCampaignReadDetail(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: LocalizableString
    slug: str
    links: list[LinkSchema] = []
