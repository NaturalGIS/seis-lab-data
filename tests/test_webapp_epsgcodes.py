import pytest

from seis_lab_data.webapp import epsgcodes


@pytest.mark.parametrize(
    "search_value",
    [
        pytest.param("376", id="code_prefix"),
        pytest.param("PORTUGAL tm06", id="name_in_any_case"),
    ],
)
def test_find_epsg_code_suggestions_matches_code_or_name(search_value):
    suggestions = epsgcodes.find_epsg_code_suggestions(search_value)
    assert ("3763", "ETRS89 / Portugal TM06") in suggestions


def test_find_epsg_code_suggestions_lists_code_matches_first_and_caps_them():
    # many names contain "zone 37", these must not push the 37xx codes out
    suggestions = epsgcodes.find_epsg_code_suggestions("37")
    assert len(suggestions) == 15
    assert all(code.startswith("37") for code, _name in suggestions)


def test_find_epsg_code_suggestions_hides_deprecated_codes():
    # EPSG:2008 is deprecated but still accepted by parse_epsg_code
    suggestions = epsgcodes.find_epsg_code_suggestions("2008")
    assert "2008" not in [code for code, _name in suggestions]
