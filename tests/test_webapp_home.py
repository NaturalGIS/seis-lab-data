"""Home page

The home page introduces the application and shows the most recent survey missions the
visitor is allowed to see. Its footer, shared by every page, links to the documentation
of the application and of its STAC API.
"""

import datetime as dt
import re

import pytest
import sqlmodel
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import user as user_schemas
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration


def test_home_shows_introduction(test_client: TestClient, db):
    """The home page shows the application title and a recent missions section, which
    states that no survey missions are found when the catalog is empty.
    """
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    assert 'aria-label="title">SeisLabData</h1>' in response.text
    assert "Recent missions" in response.text
    assert "No survey missions found" in response.text


def test_home_hides_unpublished_missions_from_anonymous_users(
    test_client: TestClient, sample_survey_missions
):
    """The home page does not show draft survey missions to anonymous visitors."""
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    for mission in sample_survey_missions:
        assert mission.name not in response.text
    assert "No survey missions found" in response.text


def test_home_shows_three_most_recent_missions(
    test_client: TestClient, sync_db_engine, published_sample_data
):
    """The home page shows the three survey missions with the most recent temporal
    extent, most recent first.
    """
    missions = published_sample_data["missions"]
    assert len(missions) > 3
    with sqlmodel.Session(sync_db_engine) as session:
        for index, mission in enumerate(missions):
            db_mission = session.get(models.SurveyMission, mission.id)
            db_mission.temporal_extent_begin = dt.date(2000 + index, 1, 1)
            db_mission.temporal_extent_end = dt.date(2000 + index, 12, 31)
            session.add(db_mission)
        session.commit()
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    expected = [m.name for m in reversed(missions)][:3]
    positions = [response.text.find(name) for name in expected]
    assert all(pos != -1 for pos in positions)
    assert positions == sorted(positions)
    for mission in missions[:-3]:
        assert mission.name not in response.text


def test_home_highlights_unpublished_missions(
    test_client: TestClient, monkeypatch, sample_survey_missions
):
    """For a catalog editor, the home page includes unpublished survey missions among
    the recent ones and marks them as unpublished.
    """

    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), user_schemas.User(
            id=identifiers.UserId("some-admin"),
            email="admin@example.com",
            username="admin",
            roles=[constants.ROLE_EDITOR],
            active=True,
        )

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    assert response.text.count("item-unpublished") == 3


@pytest.mark.parametrize(
    "language, expected_docs_url",
    [
        pytest.param("en", "https://docs.example.com/en/", id="english"),
        pytest.param("pt", "https://docs.example.com/", id="portuguese"),
    ],
)
def test_footer_links_to_the_documentation_in_the_language_of_the_user(
    test_client: TestClient, db, settings, monkeypatch, language, expected_docs_url
):
    """The page footer links to the documentation of the application, in the language
    of the user.
    """
    monkeypatch.setattr(settings, "docs_url", "https://docs.example.com/")
    response = test_client.get("/", params={"lang": language})
    assert response.status_code == 200
    assert re.search(
        rf'href="{re.escape(expected_docs_url)}"[^>]*>.*?Documenta', response.text
    )


def test_footer_links_to_the_stac_api_documentation(test_client: TestClient, db):
    """The page footer links to the interactive documentation of the STAC API."""
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    assert re.search(r'href="[^"]*/stac/docs"[^>]*>.*?STAC API</a>', response.text)

    stac_docs_response = test_client.get("/stac/docs")
    assert stac_docs_response.status_code == 200
