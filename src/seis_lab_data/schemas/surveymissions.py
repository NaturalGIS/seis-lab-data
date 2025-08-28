import uuid

import pydantic

from .common import (
    LinkSchema,
    AtLeastEnglishLocalizableString,
)


class SurveyMissionCreate(pydantic.BaseModel):
    id: uuid.UUID
    marine_campaign_id: uuid.UUID
    owner: str
    name: AtLeastEnglishLocalizableString
    links: list[LinkSchema] = []
