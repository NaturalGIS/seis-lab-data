"""Tests of the UI localization: translation catalogs and locale selection."""

import pytest
from babel.messages.pofile import read_po
from starlette.requests import HTTPConnection
from typer.testing import CliRunner

from seis_lab_data import (
    config,
    errors,
)
from seis_lab_data.cliapp.main import app
from seis_lab_data.webapp.middleware import LocaleFromAcceptLanguageHeader

TRANSLATIONS_DIR = config.SeisLabDataSettings().translations_dir
PORTUGUESE_CATALOG_PATH = TRANSLATIONS_DIR / "pt/LC_MESSAGES/messages.po"


def test_portuguese_catalog_translates_every_message(tmp_path):
    template_catalog_path = tmp_path / "messages.pot"
    result = CliRunner().invoke(
        app,
        ["translations", "extract", "--output-path", str(template_catalog_path)],
    )
    assert result.exit_code == 0, result.output
    with template_catalog_path.open() as fh:
        template_catalog = read_po(fh)
    with PORTUGUESE_CATALOG_PATH.open() as fh:
        catalog = read_po(fh)
    untranslated = [
        message.id
        for message in template_catalog
        if message.id
        and (
            (translated := catalog.get(message.id)) is None
            or not translated.string
            or translated.fuzzy
        )
    ]
    assert untranslated == [], (
        "messages missing a (non-fuzzy) portuguese translation - run the "
        "`seis-lab-data translations extract` and `update` commands, then "
        "translate them"
    )


@pytest.mark.parametrize(
    "accept_language, expected",
    [
        pytest.param("en", "en", id="exact"),
        pytest.param("en-US", "en", id="region-subtag"),
        pytest.param("EN-us", "en", id="case-insensitive"),
        pytest.param("pt-PT", "pt", id="portuguese-region"),
        pytest.param("en-GB,pt;q=0.8", "en", id="first-of-several"),
        pytest.param("en;q=0.5,pt-BR;q=0.9", "pt", id="highest-quality"),
        pytest.param("fr-FR,fr;q=0.9,en;q=0.8", "en", id="unsupported-skipped"),
        pytest.param("en;q=0,pt;q=0.1", "pt", id="zero-quality-excluded"),
        pytest.param("de", None, id="unsupported"),
        pytest.param("*", None, id="wildcard"),
        pytest.param("", None, id="empty"),
    ],
)
def test_locale_from_accept_language_header(accept_language, expected):
    connection = HTTPConnection(
        {
            "type": "http",
            "headers": [(b"accept-language", accept_language.encode())],
        }
    )
    selector = LocaleFromAcceptLanguageHeader(["pt", "en"])
    assert selector(connection) == expected


@pytest.mark.parametrize("locale", ["en", "pt"])
def test_catalog_translations_keep_the_placeholders_of_their_messages(locale):
    with (TRANSLATIONS_DIR / locale / "LC_MESSAGES/messages.po").open() as fh:
        catalog = read_po(fh)
    assert [
        (message.id, [str(error) for error in message_errors])
        for message, message_errors in catalog.check()
    ] == []


def test_error_keeps_its_message_template_apart_from_its_values():
    error = errors.SeisLabDataError(
        errors.N_("Project %(id)s does not exist."), id="p1"
    )

    assert str(error) == "Project p1 does not exist."
    assert error.message == "Project %(id)s does not exist."
    assert error.params == {"id": "p1"}


def test_error_without_values_keeps_its_message_as_is():
    assert str(errors.SeisLabDataError("100% broken")) == "100% broken"
