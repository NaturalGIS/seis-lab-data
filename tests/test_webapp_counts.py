import re
import urllib.parse

import pytest
import sqlmodel
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models
from seis_lab_data.operations import (
    projects as project_ops,
    surveymissions as mission_ops,
    surveyrelatedrecords as record_ops,
)
from seis_lab_data.schemas import (
    identifiers,
    user as user_schemas,
)
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration

_USER = user_schemas.User(
    id=identifiers.UserId("some-user"),
    email="user@example.com",
    username="user",
    roles=[],
    active=True,
)


@pytest.fixture
def logged_in(monkeypatch):
    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), _USER

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


@pytest.fixture
def mixed_sample_data(
    sync_db_engine, published_sample_data, bootstrap_dataset_categories
):
    """Published sample data, with its second record moved back to draft.

    The first record is also moved to another dataset category and loses its
    workflow stage.
    """
    first_record, second_record = published_sample_data["records"][:2]
    other_category = next(
        c for c in bootstrap_dataset_categories if c.name != "bathymetry"
    )
    with sqlmodel.Session(sync_db_engine) as session:
        db_first = session.get(models.SurveyRelatedRecord, first_record.id)
        db_first.dataset_category_id = other_category.id
        db_first.workflow_stage_id = None
        session.add(db_first)
        db_second = session.get(models.SurveyRelatedRecord, second_record.id)
        db_second.status = constants.SurveyRelatedRecordStatus.DRAFT
        session.add(db_second)
        session.commit()
    return {
        **published_sample_data,
        "first_record": first_record,
        "second_record": second_record,
        "other_category": other_category,
    }


def _get_project(mixed_sample_data):
    first_record = mixed_sample_data["first_record"]
    mission = next(
        m
        for m in mixed_sample_data["missions"]
        if m.id == first_record.survey_mission_id
    )
    return next(p for p in mixed_sample_data["projects"] if p.id == mission.project_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("initiator", [None, _USER])
async def test_count_project_contents(
    db_session_maker, sample_survey_related_records, sample_survey_missions, initiator
):
    project_ids = list({m.project_id for m in sample_survey_missions})
    async with db_session_maker() as session:
        counts = await project_ops.count_project_contents(
            session, initiator, project_ids
        )
    for project_id in project_ids:
        missions = [m for m in sample_survey_missions if m.project_id == project_id]
        records = [
            r
            for r in sample_survey_related_records
            if r.survey_mission_id in {m.id for m in missions}
        ]
        # the sample data is all in draft, which anonymous users cannot see
        expected_missions = len(missions) if initiator else 0
        expected_records = len(records) if initiator else 0
        assert counts[project_id].num_survey_missions == expected_missions
        assert counts[project_id].num_survey_related_records == expected_records


@pytest.mark.asyncio
@pytest.mark.parametrize("initiator", [None, _USER])
async def test_count_survey_mission_contents(
    db_session_maker, sample_survey_related_records, sample_survey_missions, initiator
):
    mission_ids = [m.id for m in sample_survey_missions]
    async with db_session_maker() as session:
        counts = await mission_ops.count_survey_mission_contents(
            session, initiator, mission_ids
        )
    for mission_id in mission_ids:
        records = [
            r
            for r in sample_survey_related_records
            if r.survey_mission_id == mission_id
        ]
        assert counts[mission_id].num_survey_missions is None
        assert counts[mission_id].num_survey_related_records == (
            len(records) if initiator else 0
        )


@pytest.mark.asyncio
async def test_summarize_survey_related_records(db_session_maker, mixed_sample_data):
    project = _get_project(mixed_sample_data)
    other_category = mixed_sample_data["other_category"]
    async with db_session_maker() as session:
        anonymous_summary = await record_ops.summarize_survey_related_records(
            session, None, project_id=project.id
        )
        user_summary = await record_ops.summarize_survey_related_records(
            session, _USER, project_id=project.id
        )
    # anonymous users only get the published first record
    assert [(c.name, c.count) for c in anonymous_summary.dataset_categories] == [
        (other_category.name, 1)
    ]
    assert [(s.id, s.name, s.count) for s in anonymous_summary.workflow_stages] == [
        (None, None, 1)
    ]
    assert sorted((c.name, c.count) for c in user_summary.dataset_categories) == sorted(
        [(other_category.name, 1), ("bathymetry", 1)]
    )
    assert sorted((s.name or "", s.count) for s in user_summary.workflow_stages) == [
        ("", 1),
        ("raw data", 1),
    ]


@pytest.mark.asyncio
async def test_summarize_survey_related_records_of_a_mission(
    db_session_maker, mixed_sample_data
):
    second_record = mixed_sample_data["second_record"]
    async with db_session_maker() as session:
        summary = await record_ops.summarize_survey_related_records(
            session, _USER, survey_mission_id=second_record.survey_mission_id
        )
    assert [(c.name, c.count) for c in summary.dataset_categories] == [
        ("bathymetry", 1)
    ]


def test_project_detail_shows_visible_record_summary(
    test_client: TestClient, mixed_sample_data
):
    project = _get_project(mixed_sample_data)
    other_category = mixed_sample_data["other_category"]
    response = test_client.get(f"/projects/{project.id}", params={"lang": "en"})
    assert response.status_code == 200
    assert re.search(
        r'aria-label="num-survey-related-records"\s*><span[^>]*>[^<]*</span>1<',
        response.text,
    )
    assert "bathymetry" not in response.text
    expected_link = (
        "/survey-related-records/?"
        + urllib.parse.urlencode({"filterProject": f"{project.name} - {project.id}"})
        + f"&filterDatasetCategory={other_category.id}"
    )
    assert expected_link in response.text


def test_project_detail_shows_all_records_to_logged_in_users(
    test_client: TestClient, logged_in, mixed_sample_data
):
    project = _get_project(mixed_sample_data)
    response = test_client.get(f"/projects/{project.id}", params={"lang": "en"})
    assert response.status_code == 200
    assert re.search(
        r'aria-label="num-survey-related-records"\s*><span[^>]*>[^<]*</span>2<',
        response.text,
    )
    assert "bathymetry" in response.text


def test_mission_detail_badges_filter_the_record_listing(
    test_client: TestClient, mixed_sample_data
):
    first_record = mixed_sample_data["first_record"]
    other_category = mixed_sample_data["other_category"]
    response = test_client.get(
        f"/survey-missions/{first_record.survey_mission_id}", params={"lang": "en"}
    )
    assert response.status_code == 200
    assert re.search(
        r'aria-label="num-survey-related-records"\s*><span[^>]*>[^<]*</span>1<',
        response.text,
    )
    assert f"$filterDatasetCategory = '{other_category.id}'" in response.text


def test_project_list_counts_only_visible_resources(
    test_client: TestClient, mixed_sample_data
):
    project = _get_project(mixed_sample_data)
    response = test_client.get("/projects/", params={"lang": "en"})
    assert response.status_code == 200
    card = response.text[response.text.find(project.name) :]
    num_missions = len(
        [m for m in mixed_sample_data["missions"] if m.project_id == project.id]
    )
    assert f"directions_boat</span>{num_missions}" in card
    assert "source</span>1" in card


def test_records_list_shows_the_filters_of_the_url(
    test_client: TestClient, mixed_sample_data
):
    project = _get_project(mixed_sample_data)
    other_category = mixed_sample_data["other_category"]
    project_filter = f"{project.name} - {project.id}"
    response = test_client.get(
        "/survey-related-records/",
        params={
            "lang": "en",
            "filterProject": project_filter,
            "filterDatasetCategory": str(other_category.id),
        },
    )
    assert response.status_code == 200
    assert f'value="{project_filter}"' in response.text
    assert f'<option selected value="{other_category.id}">' in response.text
    assert 'class="row collapse show" id="advanced-search-controls"' in response.text
    assert mixed_sample_data["first_record"].name in response.text
    assert mixed_sample_data["second_record"].name not in response.text
