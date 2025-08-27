import uuid

import pydantic
from slugify import slugify

from .common import (
    LinkSchema,
)


class MarineCampaignCreate(pydantic.BaseModel):
    id: uuid.UUID
    owner: str
    name: dict[str, str]
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
    name: dict[str, str]
    slug: str
    links: list[LinkSchema] = []
