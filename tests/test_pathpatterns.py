import pytest

from seis_lab_data import pathpatterns


@pytest.mark.parametrize(
    "relative_path_regexp, relative_path, expected",
    [
        pytest.param(r"s01/.*\.tif", "s01/a/b/x.tif", True, id="any depth"),
        pytest.param(r"s01/.*\.tif", "s02/s01/x.tif", False, id="fixed prefix"),
        pytest.param(r"s01/.*\.tif", "s01/x.tif.aux.xml", False, id="anchored name"),
        pytest.param(r".*_Data/.*\.kmall", "02_Data/x/f.kmall", True, id="directory"),
        pytest.param(r".*_Data/.*\.kmall", "f.kmall", False, id="missing directory"),
        pytest.param("s01/grid.tif", "s01/grid.tif", True, id="literal"),
        pytest.param(r"/s01/.*\.tif", "s01/x.tif", True, id="leading slash"),
        pytest.param(r"s01/(.*\.tif", "s01/x.tif", False, id="invalid regexp"),
    ],
)
def test_path_matches_pattern(relative_path_regexp, relative_path, expected):
    assert (
        pathpatterns.path_matches_pattern(relative_path_regexp, relative_path)
        is expected
    )
