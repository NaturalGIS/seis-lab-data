import pytest
import sqlmodel
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models

pytestmark = pytest.mark.integration

_THUMBNAIL = b"fake webp payload"


def test_survey_mission_thumbnail_is_served_only_when_visible(
    test_client: TestClient, sync_db_engine, published_sample_data
):
    with_thumbnail, without_thumbnail, *_ = published_sample_data["missions"]
    with sqlmodel.Session(sync_db_engine) as session:
        mission = session.get(models.SurveyMission, with_thumbnail.id)
        mission.thumbnail = _THUMBNAIL
        session.add(mission)
        session.commit()

    response = test_client.get(f"/survey-missions/{with_thumbnail.id}/thumbnail")
    assert response.status_code == 200
    assert response.content == _THUMBNAIL
    assert response.headers["content-type"] == "image/webp"
    listing = test_client.get("/survey-missions/", params={"lang": "en"})
    assert f"/survey-missions/{with_thumbnail.id}/thumbnail" in listing.text
    assert f"/survey-missions/{without_thumbnail.id}/thumbnail" not in listing.text

    response = test_client.get(f"/survey-missions/{without_thumbnail.id}/thumbnail")
    assert response.status_code == 404

    # a draft survey mission is hidden from anonymous users, thumbnail included
    with sqlmodel.Session(sync_db_engine) as session:
        mission = session.get(models.SurveyMission, with_thumbnail.id)
        mission.status = constants.SurveyMissionStatus.DRAFT
        session.add(mission)
        session.commit()
    response = test_client.get(f"/survey-missions/{with_thumbnail.id}/thumbnail")
    assert response.status_code == 404
