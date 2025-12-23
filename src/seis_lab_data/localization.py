from .schemas.common import Localizable


def translate_localizable(
    value: Localizable,
    current_lang: str,
) -> str:
    return getattr(value, current_lang, value.en) or ""
