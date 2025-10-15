"""Custom jinja filters."""

import logging
import typing

from jinja2 import pass_context

from ..constants import TranslatableEnumProtocol
from ..schemas.common import Localizable

logger = logging.getLogger(__name__)


@pass_context
def translate_localizable_string(
    context: dict[str, typing.Any], value: Localizable
) -> str:
    current_lang = context["request"].state.language
    return getattr(value, current_lang, value.en) or ""


def translate_enum(value: TranslatableEnumProtocol) -> str:
    return value.get_translated_value()
