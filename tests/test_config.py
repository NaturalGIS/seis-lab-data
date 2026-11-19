"""System configuration

The system configuration includes the version of the running system, which is shown
in the web interface and in the STAC API.
"""

import pytest

from seis_lab_data import config


@pytest.mark.parametrize(
    ("git_commit", "git_tag", "git_branch", "expected"),
    [
        pytest.param(
            "9fe7508c32cfca04098dd1b4599f35031fdfd814",
            "v1.0.0",
            None,
            "v1.0.0",
            id="tagged-release",
        ),
        pytest.param(
            "9fe7508c32cfca04098dd1b4599f35031fdfd814",
            "",
            "main",
            "main (9fe7508)",
            id="branch",
        ),
        pytest.param(None, None, None, "development", id="development"),
        pytest.param("", "", "", "development", id="empty-build-args"),
    ],
)
def test_system_version(git_commit, git_tag, git_branch, expected):
    """The version of the system is the release tag for a tagged release, the branch
    name and abbreviated commit identifier for any other build, and "development" when
    no commit information is available.
    """
    settings = config.SeisLabDataSettings(
        git_commit=git_commit, git_tag=git_tag, git_branch=git_branch
    )
    assert settings.version == expected
