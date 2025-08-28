from typing import Annotated

import babel
from pydantic import (
    AfterValidator,
    BaseModel,
)


def has_valid_locales(value: dict[str, str]):
    try:
        for key in value.keys():
            babel.Locale.parse(key)
    except babel.UnknownLocaleError as exc:
        raise ValueError(exc) from exc
    return value


LocalizableString = Annotated[dict[str, str], AfterValidator(has_valid_locales)]


class LinkSchema(BaseModel):
    url: str
    media_type: str
    relation: str
    description: LocalizableString
