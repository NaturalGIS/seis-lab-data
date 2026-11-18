"""Search controls of list pages

The project, survey mission and survey-related record pages keep the search filters
chosen by the user, suggest names as the user types, and offer each user only the
options and entries they are allowed to see.
"""

import dataclasses
import inspect
import json
import re
import urllib.parse
import uuid

import pytest
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data.db.commands import projects as project_commands
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.schemas import events as event_schemas
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import projects as project_schemas
from seis_lab_data.schemas import surveyrelatedrecords as record_schemas
from seis_lab_data.schemas import user as user_schemas
from seis_lab_data.tasks import surveyrelatedrecords as record_tasks
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration

_USER = user_schemas.User(
    id=identifiers.UserId("some-user"),
    email="user@example.com",
    username="user",
    roles=[],
    active=True,
)


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


@pytest.fixture
def logged_in(monkeypatch):
    """Authenticate every request as a user without roles."""

    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), _USER

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


def _get_page_urls(published_sample_data) -> list[str]:
    project = published_sample_data["projects"][0]
    mission = published_sample_data["missions"][0]
    return [
        "/projects/",
        "/survey-missions/",
        "/survey-related-records/",
        f"/projects/{project.id}",
        f"/survey-missions/{mission.id}",
    ]


def test_status_filter_is_hidden_from_anonymous_visitors(
    test_client: TestClient, published_sample_data
):
    """The status filter is not shown to anonymous visitors on the list pages and on the
    project and survey mission pages.
    """
    for url in _get_page_urls(published_sample_data):
        response = test_client.get(url, params={"lang": "en"})
        assert response.status_code == 200, url
        assert 'id="search-status"' not in response.text, url


def test_status_filter_is_shown_to_logged_in_users(
    test_client: TestClient, logged_in, published_sample_data
):
    """The status filter is shown to logged-in users on the list pages and on the
    project and survey mission pages, among the advanced search controls.
    """
    for url in _get_page_urls(published_sample_data):
        response = test_client.get(url, params={"lang": "en"})
        assert response.status_code == 200, url
        assert 'id="search-status"' in response.text, url
        assert "filterOnlyInternal" not in response.text, url
        # the status select is one of the advanced search controls
        panel = re.search(
            r'class="row collapse[^"]*" id="[a-z-]*advanced-search-controls"',
            response.text,
        )
        assert panel.start() < response.text.index('id="search-status"'), url


def test_a_status_filter_opens_the_advanced_search_controls(
    test_client: TestClient, logged_in, published_sample_data
):
    """When a page is opened with a status filter already set, the advanced search
    controls are shown expanded, with that status selected.
    """
    for url in _get_page_urls(published_sample_data):
        response = test_client.get(url, params={"filterStatus": "published"})
        assert response.status_code == 200, url
        assert re.search(
            r'class="row collapse show[^"]*" id="[a-z-]*advanced-search-controls"',
            response.text,
        ), url
        assert '<option selected value="published">' in response.text, url


def test_project_detail_ignores_a_project_filter_param(
    test_client: TestClient, published_sample_data
):
    """A project page, and the list of its survey missions, open normally when the page
    address carries a filter for another project.
    """
    project = published_sample_data["projects"][0]
    other_project_id = str(uuid.uuid4())
    response = test_client.get(
        f"/projects/{project.id}", params={"projectId": other_project_id}
    )
    assert response.status_code == 200
    component_url = test_client.app.url_path_for(
        "projects:get_project_missions_list_component", project_id=str(project.id)
    )
    response = test_client.get(
        component_url, params={"datastar": json.dumps({"projectId": other_project_id})}
    )
    assert response.status_code == 200


def test_records_list_shows_the_filters_of_its_url(
    test_client: TestClient, logged_in, published_sample_data
):
    """The survey-related record list page shows, already filled in, the filters given
    in its address (status, project, media type, asset path, start date and map area),
    with the advanced search controls expanded.
    """
    project = published_sample_data["projects"][0]
    project_filter = f"{project.name} - {project.id}"
    response = test_client.get(
        "/survey-related-records/",
        params={
            "lang": "en",
            "filterStatus": "draft",
            "filterProject": project_filter,
            "filterMediaType": "image/tiff",
            "assetPathFragment": "some/path",
            "temporalExtentBegin": "2020-01-01",
            "filterByMapArea": "true",
            "minLon": "-10",
            "minLat": "36",
            "maxLon": "-6",
            "maxLat": "42",
        },
    )
    assert response.status_code == 200
    text = response.text
    assert re.search(r'<option selected value="draft">', text)
    assert f'value="{project_filter}"' in text
    assert 'value="image/tiff"' in text
    assert 'value="some/path"' in text
    assert 'value="2020-01-01"' in text
    map_area_switch = text[text.index('id="search-map-area"') :]
    assert "checked" in map_area_switch[: map_area_switch.index("<label")]
    assert 'class="row collapse show" id="advanced-search-controls"' in text


def test_mission_detail_shows_the_filters_of_its_url(
    test_client: TestClient, logged_in, published_sample_data
):
    """A survey mission page shows, already filled in, the record filters given in its
    address (status, dataset category and asset path), with the advanced search controls
    expanded.
    """
    mission = published_sample_data["missions"][0]
    first_record = published_sample_data["records"][0]
    response = test_client.get(
        f"/survey-missions/{mission.id}",
        params={
            "lang": "en",
            "filterStatus": "published",
            "filterDatasetCategory": str(first_record.dataset_category_id),
            "assetPathFragment": "some/path",
        },
    )
    assert response.status_code == 200
    text = response.text
    assert re.search(r'<option selected value="published">', text)
    assert re.search(
        rf'<option selected value="{first_record.dataset_category_id}">', text
    )
    assert 'value="some/path"' in text
    assert 'id="mission-advanced-search-controls"' in text
    assert 'class="row collapse show" id="mission-advanced-search-controls"' in text


def test_records_list_component_url_keeps_reserved_characters(
    test_client: TestClient, published_sample_data
):
    """Search text containing special characters, such as the ampersand and the equals
    sign, is kept intact when the record list is refreshed.
    """
    response = test_client.get(
        test_client.app.url_path_for("survey_related_records:get_list_component"),
        params={"datastar": json.dumps({"search": "a&b=c"})},
    )
    assert response.status_code == 200
    assert urllib.parse.urlencode({"search": "a&b=c"}) in response.text


@pytest.mark.asyncio
async def test_bulk_update_of_all_matching_records_stays_in_its_survey_mission(
    db_session_maker, settings, admin_user, sample_survey_related_records, monkeypatch
):
    """A bulk update of all the records matching a search within one survey mission
    changes only the records of that survey mission, and reports the number of records
    changed accordingly.
    """
    first_record, second_record = sample_survey_related_records
    assert first_record.survey_mission_id != second_record.survey_mission_id
    # the test settings have no message broker to dispatch the events through
    monkeypatch.setattr(settings, "_event_dispatcher", _EventCollector())
    selection = record_schemas.SurveyRelatedRecordSelection(
        survey_mission_id=identifiers.SurveyMissionId(first_record.survey_mission_id)
    )
    to_update = record_schemas.SurveyRelatedRecordBulkUpdate(
        description="A bulk-updated description"
    )
    # unwrapped, as the actors only run inside a worker
    await inspect.unwrap(record_tasks.bulk_update_survey_related_records.fn)(
        raw_request_id=str(uuid.uuid4()),
        raw_to_update=to_update.model_dump_json(exclude_unset=True),
        raw_selection=selection.model_dump_json(exclude_unset=True),
        raw_initiator=json.dumps(dataclasses.asdict(admin_user)),
        settings=settings,
    )
    async with db_session_maker() as session:
        updated = await record_queries.get_survey_related_record(
            session, identifiers.SurveyRelatedRecordId(first_record.id)
        )
        untouched = await record_queries.get_survey_related_record(
            session, identifiers.SurveyRelatedRecordId(second_record.id)
        )
    assert updated.description == "A bulk-updated description"
    assert untouched.description != "A bulk-updated description"
    assert settings.get_event_dispatcher().events[-1].affected_count == 1


def _get_project_with_missions(published_sample_data):
    mission = published_sample_data["missions"][0]
    project = next(
        p for p in published_sample_data["projects"] if p.id == mission.project_id
    )
    other_project = next(
        p for p in published_sample_data["projects"] if p.id != mission.project_id
    )
    return project, other_project


def test_missions_list_filters_by_parent_project(
    test_client: TestClient, published_sample_data
):
    """Filtering the survey mission list by project shows only the survey missions of
    that project, with the filter filled in and the advanced search controls expanded.
    """
    project, _ = _get_project_with_missions(published_sample_data)
    project_filter = f"{project.name} - {project.id}"
    response = test_client.get(
        "/survey-missions/", params={"lang": "en", "filterProject": project_filter}
    )
    assert response.status_code == 200
    assert f'value="{project_filter}"' in response.text
    assert 'class="row collapse show" id="advanced-search-controls"' in response.text
    for mission in published_sample_data["missions"]:
        shown = f"/survey-missions/{mission.id}" in response.text
        assert shown is (mission.project_id == project.id), mission.name


def test_project_detail_lists_its_own_missions_despite_a_project_filter(
    test_client: TestClient, published_sample_data
):
    """A project page lists all of its own survey missions even when its address carries
    a filter for another project.
    """
    project, other_project = _get_project_with_missions(published_sample_data)
    response = test_client.get(
        f"/projects/{project.id}",
        params={"filterProject": f"{other_project.name} - {other_project.id}"},
    )
    assert response.status_code == 200
    for mission in published_sample_data["missions"]:
        if mission.project_id == project.id:
            assert f"/survey-missions/{mission.id}" in response.text


def test_project_detail_shows_the_mission_filters_of_its_url(
    test_client: TestClient, published_sample_data
):
    """A project page shows, already filled in, the survey mission filters given in its
    address (end date and map area), along with its map and the advanced search controls
    expanded.
    """
    project, _ = _get_project_with_missions(published_sample_data)
    response = test_client.get(
        f"/projects/{project.id}",
        params={
            "lang": "en",
            "temporalExtentEnd": "2030-12-31",
            "filterByMapArea": "true",
            "minLon": "-10",
            "minLat": "36",
            "maxLon": "-6",
            "maxLat": "42",
        },
    )
    assert response.status_code == 200
    text = response.text
    assert 'value="2030-12-31"' in text
    assert "<base-map" in text
    map_area_switch = text[text.index('id="search-map-area"') :]
    assert "checked" in map_area_switch[: map_area_switch.index("<label")]
    assert 'show mb-3" id="project-advanced-search-controls"' in text


def test_project_missions_component_applies_the_map_area(
    test_client: TestClient, published_sample_data
):
    """When the survey missions of a project page are filtered by map area, the filter
    is kept in the refreshed list and the map of the survey missions is updated along
    with it.
    """
    project, _ = _get_project_with_missions(published_sample_data)
    component_url = test_client.app.url_path_for(
        "projects:get_project_missions_list_component", project_id=str(project.id)
    )
    signals = {
        "filterByMapArea": True,
        "minLon": -10,
        "minLat": 36,
        "maxLon": -6,
        "maxLat": 42,
    }
    response = test_client.get(component_url, params={"datastar": json.dumps(signals)})
    assert response.status_code == 200
    assert urllib.parse.urlencode({"filterByMapArea": "true"}) in response.text
    # the map of the missions is updated along with the listing
    assert "getSource('polygons').setData" in response.text


def _get_datalist_suggestions(
    test_client: TestClient,
    route_name: str,
    signal: str,
    typed: str,
    other_signals: dict | None = None,
) -> str:
    response = test_client.get(
        test_client.app.url_path_for(route_name),
        params={
            "target": "some-datalist",
            "signal": signal,
            "datastar": json.dumps({signal: typed, **(other_signals or {})}),
        },
    )
    assert response.status_code == 200
    return response.text


@pytest.mark.asyncio
async def test_project_suggestions_reach_beyond_the_first_page(
    test_client: TestClient, logged_in, db, db_session_maker, settings
):
    # more projects than a page holds, the searched one sorting last
    """Project name suggestions include matching projects beyond the first page of
    results, leave out projects that do not match the typed text, and display names
    containing quotes correctly.
    """
    async with db_session_maker() as session:
        for index in range(settings.pagination_page_size + 5):
            await project_commands.create_project(
                session,
                project_schemas.ProjectCreate(
                    id=identifiers.ProjectId(uuid.uuid4()),
                    name=f"Filler project {index:02d}",
                ),
            )
        searched_id = uuid.uuid4()
        await project_commands.create_project(
            session,
            project_schemas.ProjectCreate(
                id=identifiers.ProjectId(searched_id),
                name='Zé\'s "quoted" survey',
            ),
        )
    suggestions = _get_datalist_suggestions(
        test_client, "projects:get_datalist", "filterProject", "quoted"
    )
    assert 'id="some-datalist"' in suggestions
    # the name's quotes are escaped inside the option's value
    assert (
        f'<option value="Zé&#x27;s &quot;quoted&quot; survey - {searched_id}">'
        in suggestions
    )
    assert "Filler project" not in suggestions


def test_mission_suggestions_only_include_what_visitors_may_see(
    test_client: TestClient, sample_survey_missions
):
    # the sample missions are drafts, hidden from anonymous visitors
    """Survey mission name suggestions offered to anonymous visitors do not include
    draft survey missions.
    """
    mission = sample_survey_missions[0]
    suggestions = _get_datalist_suggestions(
        test_client, "survey_missions:get_datalist", "filterMission", mission.name
    )
    assert str(mission.id) not in suggestions


def test_mission_suggestions_match_the_typed_name(
    test_client: TestClient, logged_in, sample_survey_missions
):
    """Survey mission name suggestions offered to logged-in users include the survey
    mission whose name was typed.
    """
    mission = sample_survey_missions[0]
    suggestions = _get_datalist_suggestions(
        test_client, "survey_missions:get_datalist", "filterMission", mission.name
    )
    assert f" - {mission.id}" in suggestions


@pytest.mark.parametrize(
    "url, expected_suggestion_urls",
    [
        pytest.param("/survey-missions/", ["/projects/datalist"], id="missions"),
        pytest.param(
            "/survey-related-records/",
            ["/projects/datalist", "/survey-missions/datalist"],
            id="records",
        ),
    ],
)
def test_list_pages_fetch_suggestions_for_their_pickers(
    test_client: TestClient, published_sample_data, url, expected_suggestion_urls
):
    """As the user types in the project and survey mission pickers of the survey mission
    and survey-related record list pages, matching suggestions are requested from the
    server.
    """
    response = test_client.get(url)
    assert response.status_code == 200
    for suggestion_url in expected_suggestion_urls:
        assert re.search(
            rf"data-on:input__debounce\.300ms=\"@get\('[^']*{suggestion_url}\?target=",
            response.text,
        ), suggestion_url


@pytest.mark.parametrize(
    "typed",
    [
        pytest.param("", id="nothing_typed"),
        pytest.param("-", id="typed_text"),
        pytest.param(
            f"some mission (some project) - {uuid.uuid4()}", id="picked_suggestion"
        ),
    ],
)
def test_mission_suggestions_are_narrowed_by_the_selected_project(
    test_client: TestClient, logged_in, sample_projects, sample_survey_missions, typed
):
    """When a project is selected, the survey mission suggestions are limited to the
    survey missions of that project, whether nothing was typed, some text was typed or a
    previous suggestion was picked.
    """
    project = next(
        p
        for p in sample_projects
        if any(m.project_id == p.id for m in sample_survey_missions)
    )
    suggestions = _get_datalist_suggestions(
        test_client,
        "survey_missions:get_datalist",
        "filterMission",
        typed,
        {"filterProject": f"{project.name} - {project.id}"},
    )
    for mission in sample_survey_missions:
        if mission.project_id == project.id and (typed != "-" or "-" in mission.name):
            assert str(mission.id) in suggestions, mission.name
        elif mission.project_id != project.id:
            assert str(mission.id) not in suggestions, mission.name


def test_records_list_mission_options_follow_the_project_of_its_url(
    test_client: TestClient, published_sample_data
):
    """On the survey-related record list page opened with a project filter, the survey
    mission picker offers only the survey missions of that project, and its suggestions
    are requested again whenever the selected project changes.
    """
    mission = published_sample_data["missions"][0]
    project = next(
        p for p in published_sample_data["projects"] if p.id == mission.project_id
    )
    response = test_client.get(
        "/survey-related-records/",
        params={"filterProject": f"{project.name} - {project.id}"},
    )
    assert response.status_code == 200
    text = response.text
    start = text.index('<datalist id="search-mission-datalist-datalist">')
    mission_options = text[start : text.index("</datalist>", start)]
    for other_mission in published_sample_data["missions"]:
        assert (str(other_mission.id) in mission_options) is (
            other_mission.project_id == project.id
        ), other_mission.name
    # the mission suggestions are fetched again when the project changes
    assert 'data-on-signal-patch-filter="{include: /^filterProject$/}"' in text
