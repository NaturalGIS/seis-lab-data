"""Asset discovery configuration forms

The forms for creating and editing asset discovery configurations explain how to write
the path pattern of the files to discover, and refer to the user guide, in the language
of the user, for its full description.
"""

import pytest
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def logged_in_as_admin(monkeypatch, admin_user):
    """Authenticate every request as the `admin_user` fixture."""

    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), admin_user

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


@pytest.mark.parametrize(
    "language, expected_guide_url",
    [
        pytest.param(
            "en",
            "https://docs.example.com/en/user-guide/#path-patterns",
            id="english",
        ),
        pytest.param(
            "pt", "https://docs.example.com/user-guide/#path-patterns", id="portuguese"
        ),
    ],
)
def test_creation_form_links_to_the_path_pattern_guide(
    test_client: TestClient,
    logged_in_as_admin,
    settings,
    monkeypatch,
    language,
    expected_guide_url,
):
    """The form for creating an asset discovery configuration links to the description
    of path patterns in the user guide, in the language of the user.
    """
    monkeypatch.setattr(settings, "docs_url", "https://docs.example.com/")

    response = test_client.get(
        "/asset-discovery-configurations/new", params={"lang": language}
    )

    assert response.status_code == 200
    assert f'href="{expected_guide_url}"' in response.text
