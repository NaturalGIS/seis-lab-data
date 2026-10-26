import datetime as dt

import pytest
import sqlmodel
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.schemas import (
    identifiers,
)
from seis_lab_data.schemas import (
    user as user_schemas,
)
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration


def test_home_shows_introduction(test_client: TestClient, db):
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    assert 'aria-label="title">SeisLabData</h1>' in response.text
    assert "Recent missions" in response.text
    assert "No survey missions found" in response.text


def test_home_hides_unpublished_missions_from_anonymous_users(
    test_client: TestClient, sample_survey_missions
):
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    for mission in sample_survey_missions:
        assert mission.name not in response.text
    assert "No survey missions found" in response.text


def test_home_shows_three_most_recent_missions(
    test_client: TestClient, sync_db_engine, published_sample_data
):
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
    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), user_schemas.User(
            id=identifiers.UserId("some-admin"),
            email="admin@example.com",
            username="admin",
            roles=[constants.ROLE_ADMIN],
            active=True,
        )

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    assert response.text.count("item-unpublished") == 3
