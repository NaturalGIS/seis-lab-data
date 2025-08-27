import pydantic


class LocalizableStringSchema(pydantic.BaseModel):
    locale: str


class LinkSchema(pydantic.BaseModel):
    url: str
    media_type: str
    relation: str
    description: dict[str, str]
