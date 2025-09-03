"""Custom jinja filters."""

import typing

from jinja2 import pass_context

from ..constants import TranslatableEnumProtocol
from ..schemas.common import AtLeastEnglishLocalizableString


@pass_context
def translate_localizable_string(
    context: dict[str, typing.Any], value: AtLeastEnglishLocalizableString
) -> str:
    current_lang = context.get("request").state.language
    return value.get(current_lang, value["en"])


def translate_enum(value: TranslatableEnumProtocol) -> str:
    return value.get_translated_value()
