"""Tests for the deletion of projects and survey missions from their detail pages."""

import pytest
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db.commands import surveyrelatedrecords as record_commands
from seis_lab_data.schemas import identifiers
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def logged_in_as_admin(monkeypatch, admin_user):
    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), admin_user

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page_resource_type",
    [
        pytest.param(constants.ResourceType.PROJECT, id="project-page"),
        pytest.param(constants.ResourceType.MISSION, id="mission-page"),
    ],
)
@pytest.mark.parametrize(
    "record_status, expected_busy",
    [
        pytest.param(
            constants.SurveyRelatedRecordStatus.UNDER_EXPORT, True, id="busy-record"
        ),
        pytest.param(
            constants.SurveyRelatedRecordStatus.DRAFT, False, id="idle-record"
        ),
    ],
)
async def test_detail_page_disables_deletion_while_records_are_busy(
    test_client: TestClient,
    db_session_maker,
    sample_survey_related_records,
    logged_in_as_admin,
    page_resource_type,
    record_status,
    expected_busy,
):
    record = sample_survey_related_records[0]
    async with db_session_maker() as session:
        await record_commands.set_survey_related_record_status(
            session, identifiers.SurveyRelatedRecordId(record.id), record_status
        )
    url = (
        f"/projects/{record.survey_mission.project_id}"
        if page_resource_type == constants.ResourceType.PROJECT
        else f"/survey-missions/{record.survey_mission_id}"
    )

    response = test_client.get(url, params={"lang": "en"})

    assert response.status_code == 200
    expected_signal = "true" if expected_busy else "false"
    assert f'data-signals:has-busy-descendants="{expected_signal}"' in response.text
    delete_button = response.text.split('aria-label="show-delete-confirmation-modal"')[
        1
    ].split(">")[0]
    assert "$hasBusyDescendants" in delete_button
    # the notice is always rendered, so that it can be shown when a record gets busy
    notice = response.text.split('aria-label="privileged-notice"')[1].split(">")[0]
    assert 'data-show="$hasBusyDescendants"' in notice
    assert ('style="display: none"' in notice) is not expected_busy
