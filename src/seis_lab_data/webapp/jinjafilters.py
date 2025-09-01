"""Custom jinja filters."""

import typing

from jinja2 import pass_context

from ..schemas.common import AtLeastEnglishLocalizableString


@pass_context
def translate_localizable_string(
    context: dict[str, typing.Any], value: AtLeastEnglishLocalizableString
) -> str:
    current_lang = context.get("request").state.language
    return value.get(current_lang, value["en"])
