from .schemas.common import Localizable


def translate_localizable(
    value: Localizable,
    current_lang: str,
) -> str:
    return getattr(value, current_lang, value.en) or ""


def translate_localizable_dict(value: dict[str, str], current_lang: str) -> str:
    return value.get(current_lang, "en") or ""
