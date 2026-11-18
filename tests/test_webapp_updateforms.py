"""Availability of edit forms

Edit forms for projects, survey missions and survey-related records are offered only to
users allowed to edit them, and only while the entry is not busy with a running task.
Otherwise the user is returned to the entry's page with an explanation.
"""

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

_EDITOR = user_schemas.User(
    id=identifiers.UserId("some-editor"),
    email="editor@example.com",
    username="editor",
    roles=[constants.ROLE_EDITOR],
    active=True,
)

_USER_WITHOUT_ROLE = user_schemas.User(
    id=identifiers.UserId("some-reader"),
    email="reader@example.com",
    username="reader",
    roles=[],
    active=True,
)

# per resource kind: its model, the base path of its routes and a busy status
_RESOURCE_KINDS = {
    "project": (
        models.Project,
        "/projects",
        constants.ProjectStatus.UNDER_VALIDATION,
    ),
    "survey mission": (
        models.SurveyMission,
        "/survey-missions",
        constants.SurveyMissionStatus.UNDER_DISCOVERY,
    ),
    "survey-related record": (
        models.SurveyRelatedRecord,
        "/survey-related-records",
        constants.SurveyRelatedRecordStatus.UNDER_EXPORT,
    ),
}


def _authenticate_as(monkeypatch: pytest.MonkeyPatch, user: user_schemas.User):
    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), user

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


def _set_status(sync_db_engine, model, item_id, status) -> None:
    with sqlmodel.Session(sync_db_engine) as session:
        item = session.get(model, item_id)
        item.status = status
        session.add(item)
        session.commit()


def _get_sample_item(published_sample_data, resource_kind: str):
    return {
        "project": published_sample_data["projects"][0],
        "survey mission": published_sample_data["missions"][0],
        "survey-related record": published_sample_data["records"][0],
    }[resource_kind]


def _assert_redirected_with_flash(
    test_client: TestClient, update_form_url: str, detail_url: str, message: str
) -> None:
    response = test_client.get(
        update_form_url, params={"lang": "en"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(detail_url)

    detail_page = test_client.get(detail_url, params={"lang": "en"})
    assert detail_page.status_code == 200
    assert "showFlash(" in detail_page.text
    assert '"category": "danger"' in detail_page.text
    assert message in detail_page.text

    # the notification is shown only once
    detail_page = test_client.get(detail_url, params={"lang": "en"})
    assert message not in detail_page.text


@pytest.mark.parametrize("resource_kind", _RESOURCE_KINDS)
def test_update_form_is_shown_for_idle_resource(
    test_client: TestClient, published_sample_data, monkeypatch, resource_kind
):
    """An editor can open the edit form of a project, survey mission or survey-related
    record that is not busy with a task.
    """
    _authenticate_as(monkeypatch, _EDITOR)
    _model, base_path, _busy_status = _RESOURCE_KINDS[resource_kind]
    item = _get_sample_item(published_sample_data, resource_kind)

    response = test_client.get(f"{base_path}/{item.id}/update", follow_redirects=False)

    assert response.status_code == 200


@pytest.mark.parametrize("resource_kind", _RESOURCE_KINDS)
def test_update_form_redirects_when_resource_is_busy(
    test_client: TestClient,
    sync_db_engine,
    published_sample_data,
    monkeypatch,
    resource_kind,
):
    """An editor who tries to edit a project, survey mission or survey-related record
    that is busy with a task, such as validation, discovery or export, is returned to
    its page, where a one-time error notification explains that its current status
    prevents updates.
    """
    _authenticate_as(monkeypatch, _EDITOR)
    model, base_path, busy_status = _RESOURCE_KINDS[resource_kind]
    item = _get_sample_item(published_sample_data, resource_kind)
    _set_status(sync_db_engine, model, item.id, busy_status)

    _assert_redirected_with_flash(
        test_client,
        update_form_url=f"{base_path}/{item.id}/update",
        detail_url=f"{base_path}/{item.id}",
        message=(
            f"Cannot update the {resource_kind} because its status is "
            f"{busy_status.get_translated_value()}."
        ),
    )


@pytest.mark.parametrize("resource_kind", _RESOURCE_KINDS)
def test_update_form_redirects_when_user_lacks_role(
    test_client: TestClient, published_sample_data, monkeypatch, resource_kind
):
    """A logged-in user without the editor role who tries to edit a project, survey
    mission or survey-related record is returned to its page, where a one-time error
    notification explains that the user is not allowed to update it.
    """
    _authenticate_as(monkeypatch, _USER_WITHOUT_ROLE)
    _model, base_path, _busy_status = _RESOURCE_KINDS[resource_kind]
    item = _get_sample_item(published_sample_data, resource_kind)

    _assert_redirected_with_flash(
        test_client,
        update_form_url=f"{base_path}/{item.id}/update",
        detail_url=f"{base_path}/{item.id}",
        message=f"User is not allowed to update the {resource_kind}.",
    )


@pytest.mark.parametrize("mission_status", constants.SURVEY_MISSION_DISCOVERY_STATUSES)
def test_record_update_form_redirects_when_mission_is_under_discovery(
    test_client: TestClient,
    sync_db_engine,
    published_sample_data,
    monkeypatch,
    mission_status,
):
    """An editor who tries to edit a survey-related record while its survey mission is
    under discovery is returned to the record page, where a one-time error notification
    explains why.
    """
    _authenticate_as(monkeypatch, _EDITOR)
    record = published_sample_data["records"][0]
    _set_status(
        sync_db_engine, models.SurveyMission, record.survey_mission_id, mission_status
    )

    _assert_redirected_with_flash(
        test_client,
        update_form_url=f"/survey-related-records/{record.id}/update",
        detail_url=f"/survey-related-records/{record.id}",
        message=(
            "Cannot update the survey-related record because its survey mission "
            "is under discovery."
        ),
    )
