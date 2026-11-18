"""Discovery on survey mission pages

Survey mission pages let catalog editors start and cancel the discovery of survey-
related records from the file archive and follow its progress. While a discovery runs,
the mission's records cannot be modified.
"""

import uuid

import pytest
from starlette.authentication import AuthCredentials
from starlette.testclient import TestClient

from seis_lab_data import (
    constants,
    errors,
)
from seis_lab_data.db.commands import surveymissions as mission_commands
from seis_lab_data.db.queries import surveyrelatedrecords as record_queries
from seis_lab_data.operations import surveyrelatedrecords as record_ops
from seis_lab_data.schemas import identifiers
from seis_lab_data.schemas import surveyrelatedrecords as record_schemas
from seis_lab_data.tasks import discovery as discovery_tasks
from seis_lab_data.webapp.auth_backend import OIDCAuthBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def logged_in_as_admin(monkeypatch, admin_user):
    """Authenticate every request as the `admin_user` fixture."""

    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), admin_user

    monkeypatch.setattr(OIDCAuthBackend, "authenticate", authenticate)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, expected_action, absent_actions",
    [
        pytest.param(
            constants.SurveyMissionStatus.DRAFT,
            "discover-mission",
            ("cancel-mission-discovery", "discovery-progress"),
            id="idle",
        ),
        pytest.param(
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
            "cancel-mission-discovery",
            ("discover-mission",),
            id="running",
        ),
        pytest.param(
            constants.SurveyMissionStatus.CANCELLING_DISCOVERY,
            "cancelling-mission-discovery",
            ("discover-mission", "cancel-mission-discovery"),
            id="cancelling",
        ),
    ],
)
async def test_mission_page_shows_the_discovery_action_of_its_status(
    test_client: TestClient,
    db_session_maker,
    sample_survey_missions,
    logged_in_as_admin,
    status,
    expected_action,
    absent_actions,
):
    """A survey mission's page offers the action that matches its discovery state:
    starting a discovery when idle, cancelling it while it runs, and an indication that
    cancellation is in progress while it is being cancelled.
    """
    mission = sample_survey_missions[0]
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, identifiers.SurveyMissionId(mission.id), status
        )

    response = test_client.get(f"/survey-missions/{mission.id}", params={"lang": "en"})

    assert response.status_code == 200
    assert f'aria-label="{expected_action}"' in response.text
    for action in absent_actions:
        assert f'aria-label="{action}"' not in response.text


@pytest.mark.parametrize(
    "status",
    [
        constants.SurveyMissionStatus.DRAFT,
        constants.SurveyMissionStatus.UNDER_DISCOVERY,
    ],
)
@pytest.mark.asyncio
async def test_mission_page_guards_discovery_actions_behind_dialogs(
    test_client: TestClient,
    db_session_maker,
    sample_survey_missions,
    logged_in_as_admin,
    status,
):
    """Starting and cancelling a discovery each require confirmation in a dialog, and
    only the button matching the survey mission's current state opens its dialog.
    """
    mission = sample_survey_missions[0]
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, identifiers.SurveyMissionId(mission.id), status
        )

    response = test_client.get(f"/survey-missions/{mission.id}", params={"lang": "en"})

    assert response.status_code == 200
    # both dialogs are always there, as status changes only morph the actions
    for modal_id, confirm_label in (
        ("discover-records-modal", "confirm-mission-discovery"),
        ("cancel-discovery-modal", "confirm-mission-discovery-cancellation"),
    ):
        assert f'id="{modal_id}"' in response.text
        assert f'aria-label="{confirm_label}"' in response.text
    assert response.text.count('data-bs-target="#discover-records-modal"') == (
        status == constants.SurveyMissionStatus.DRAFT
    )
    assert response.text.count('data-bs-target="#cancel-discovery-modal"') == (
        status == constants.SurveyMissionStatus.UNDER_DISCOVERY
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, shows_progress",
    [
        pytest.param(constants.SurveyMissionStatus.DRAFT, False, id="draft"),
        pytest.param(constants.SurveyMissionStatus.PUBLISHED, False, id="published"),
        pytest.param(
            constants.SurveyMissionStatus.UNDER_VALIDATION, False, id="other busy"
        ),
        pytest.param(
            constants.SurveyMissionStatus.UNDER_DISCOVERY, True, id="under discovery"
        ),
        pytest.param(
            constants.SurveyMissionStatus.CANCELLING_DISCOVERY, True, id="cancelling"
        ),
    ],
)
async def test_mission_page_shows_discovery_progress_in_place_of_its_status_icon(
    test_client: TestClient,
    db_session_maker,
    sample_survey_missions,
    logged_in_as_admin,
    status,
    shows_progress,
):
    """While a survey mission's discovery runs or is being cancelled, its page shows the
    discovery progress in place of the status indicator; other statuses show their usual
    indicator, and a published mission shows none.
    """
    mission = sample_survey_missions[0]
    await _set_mission_status(db_session_maker, mission.id, status)

    response = test_client.get(f"/survey-missions/{mission.id}", params={"lang": "en"})

    assert response.status_code == 200
    info_section = response.text.split('id="survey-mission-info"')[1]
    # a published mission has no status item, so that the list keeps its borders
    assert ('aria-label="status"' in info_section) is (
        status != constants.SurveyMissionStatus.PUBLISHED
    )
    status_item = info_section.split('aria-label="status"')[-1].split("</li>")[0]
    for label in (
        "discovery-sections-progress",
        "discovery-section",
        "discovery-progress",
    ):
        assert (f'aria-label="{label}"' in status_item) is shows_progress
    assert ("spinner-border" in status_item) is (
        status == constants.SurveyMissionStatus.UNDER_VALIDATION
    )


def test_cancel_discovery_requires_a_csrf_token(
    test_client: TestClient, sample_survey_missions, logged_in_as_admin, monkeypatch
):
    """A request to cancel a discovery that does not carry the page's security token is
    refused, and no cancellation takes place.
    """
    mission = sample_survey_missions[0]
    enqueued = []
    monkeypatch.setattr(
        discovery_tasks.cancel_survey_mission_discovery,
        "send",
        lambda **kwargs: enqueued.append(kwargs),
    )
    request_id = "6f1c3f0e-9a4b-4a3e-8f5e-0d6f3c2b1a90"

    response = test_client.post(
        f"/survey-missions/{mission.id}/discover/{request_id}/cancel"
    )

    assert response.status_code == 403
    assert enqueued == []


async def _set_mission_status(db_session_maker, mission_id, status):
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, identifiers.SurveyMissionId(mission_id), status
        )


def _records_of(records, mission_id):
    return [record for record in records if record.survey_mission_id == mission_id]


@pytest.mark.asyncio
async def test_details_component_is_morphed_into_the_detail_page(
    test_client: TestClient,
    db_session_maker,
    sample_survey_missions,
    logged_in_as_admin,
):
    """While a survey mission is under discovery, the refreshed mission details sent to
    its open page carry the current status, the cancel action and the discovery
    progress, and update the summary, actions and information sections without reloading
    the list of records.
    """
    mission = sample_survey_missions[0]
    await _set_mission_status(
        db_session_maker, mission.id, constants.SurveyMissionStatus.UNDER_DISCOVERY
    )
    request_id = uuid.uuid4()

    response = test_client.get(f"/survey-missions/{mission.id}/details/{request_id}")

    assert response.status_code == 200
    assert "event: datastar-patch-signals" in response.text
    assert '"status":"under_discovery"' in response.text.replace(" ", "")
    # matched by their ids and morphed, leaving alone the records list and the
    # element that keeps the page's stream open
    assert "data: selector" not in response.text
    assert 'id="survey-mission-summary"' in response.text
    assert 'id="survey-mission-actions"' in response.text
    assert 'id="survey-mission-info"' in response.text
    assert 'aria-label="cancel-mission-discovery"' in response.text
    assert 'aria-label="discovery-sections-progress"' in response.text
    # the page's own request id, which its stream filters messages by
    assert str(request_id) in response.text


def test_details_component_needs_a_valid_request_id(
    test_client: TestClient, sample_survey_missions, logged_in_as_admin
):
    """A request for refreshed survey mission details is rejected when it does not
    identify the page it is meant for.
    """
    mission = sample_survey_missions[0]

    response = test_client.get(f"/survey-missions/{mission.id}/details/nope")

    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, locked",
    [
        pytest.param(constants.SurveyMissionStatus.DRAFT, False, id="idle"),
        pytest.param(constants.SurveyMissionStatus.UNDER_DISCOVERY, True, id="running"),
        pytest.param(
            constants.SurveyMissionStatus.CANCELLING_DISCOVERY, True, id="cancelling"
        ),
    ],
)
async def test_mission_page_disables_modifications_under_discovery(
    test_client: TestClient,
    db_session_maker,
    sample_survey_missions,
    sample_survey_related_records,
    logged_in_as_admin,
    status,
    locked,
):
    """While a survey mission's discovery runs or is being cancelled, its page disables
    editing and deletion and does not offer the bulk update of its records.
    """
    mission = next(
        m
        for m in sample_survey_missions
        if _records_of(sample_survey_related_records, m.id)
    )
    await _set_mission_status(db_session_maker, mission.id, status)

    response = test_client.get(f"/survey-missions/{mission.id}", params={"lang": "en"})

    assert response.status_code == 200
    # edit and delete follow the status signal, the same as for other busy statuses
    assert "$isBusy ? 'btn btn-outline-dark disabled'" in response.text
    assert ('aria-disabled="true"' in response.text) is locked
    assert ('aria-label="bulk-update"' in response.text) is not locked


@pytest.mark.asyncio
async def test_records_list_offers_no_bulk_update_under_discovery(
    test_client: TestClient,
    db_session_maker,
    sample_survey_missions,
    sample_survey_related_records,
    logged_in_as_admin,
):
    """The bulk update of a survey mission's records is offered in its record list, and
    is no longer offered once a discovery starts.
    """
    mission = next(
        m
        for m in sample_survey_missions
        if _records_of(sample_survey_related_records, m.id)
    )
    url = f"/survey-missions/{mission.id}/records"

    assert 'aria-label="bulk-update"' in test_client.get(url).text
    await _set_mission_status(
        db_session_maker, mission.id, constants.SurveyMissionStatus.UNDER_DISCOVERY
    )
    response = test_client.get(url)

    assert response.status_code == 200
    assert 'aria-label="bulk-update"' not in response.text


@pytest.mark.asyncio
async def test_record_page_disables_modifications_under_discovery(
    test_client: TestClient,
    db_session_maker,
    sample_survey_related_records,
    logged_in_as_admin,
):
    """The page of a survey-related record disables editing and deletion while its
    survey mission is under discovery.
    """
    record = sample_survey_related_records[0]
    await _set_mission_status(
        db_session_maker,
        record.survey_mission_id,
        constants.SurveyMissionStatus.UNDER_DISCOVERY,
    )

    response = test_client.get(f"/survey-related-records/{record.id}")

    assert response.status_code == 200
    assert 'data-signals:mission-under-discovery="true"' in response.text
    assert "$isBusy || $missionUnderDiscovery" in response.text


@pytest.mark.asyncio
async def test_record_details_component_patches_the_mission_discovery_signal(
    test_client: TestClient,
    db_session_maker,
    sample_survey_related_records,
    logged_in_as_admin,
):
    """The refreshed details sent to an open survey-related record page indicate that
    the record's survey mission is under discovery.
    """
    record = sample_survey_related_records[0]
    await _set_mission_status(
        db_session_maker,
        record.survey_mission_id,
        constants.SurveyMissionStatus.UNDER_DISCOVERY,
    )

    response = test_client.get(
        f"/survey-related-records/{record.id}/details/{uuid.uuid4()}"
    )

    assert response.status_code == 200
    assert '"missionUnderDiscovery":true' in response.text.replace(" ", "")


class _EventCollector:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_records_of_a_mission_under_discovery_cannot_be_modified(
    db_session_maker, sample_survey_related_records, admin_user
):
    """While a survey mission is under discovery, records cannot be created, updated or
    deleted in it, each attempt being reported as failed with an explanation, and a bulk
    update leaves its records unchanged.
    """
    record = sample_survey_related_records[0]
    record_id = identifiers.SurveyRelatedRecordId(record.id)
    await _set_mission_status(
        db_session_maker,
        record.survey_mission_id,
        constants.SurveyMissionStatus.UNDER_DISCOVERY,
    )
    collector = _EventCollector()
    async with db_session_maker() as session:
        with pytest.raises(errors.SeisLabDataError, match="under discovery"):
            await record_ops.create_survey_related_record(
                request_id=identifiers.RequestId(uuid.uuid4()),
                to_create=record_schemas.SurveyRelatedRecordCreate(
                    id=identifiers.SurveyRelatedRecordId(uuid.uuid4()),
                    survey_mission_id=identifiers.SurveyMissionId(
                        record.survey_mission_id
                    ),
                    name="made by hand",
                    description="",
                    dataset_category_id=record.dataset_category_id,
                    workflow_stage_id=record.workflow_stage_id,
                ),
                initiator=admin_user,
                session=session,
                event_dispatcher=collector,
            )
        with pytest.raises(errors.SeisLabDataError, match="under discovery"):
            await record_ops.update_survey_related_record(
                request_id=identifiers.RequestId(uuid.uuid4()),
                survey_related_record_id=record_id,
                to_update=record_schemas.SurveyRelatedRecordUpdate(name="renamed"),
                initiator=admin_user,
                session=session,
                event_dispatcher=collector,
            )
        await record_ops.delete_survey_related_record(
            request_id=identifiers.RequestId(uuid.uuid4()),
            survey_related_record_id=record_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=collector,
        )
        updated_count = await record_ops.bulk_update_survey_related_records(
            request_id=identifiers.RequestId(uuid.uuid4()),
            to_update=record_schemas.SurveyRelatedRecordBulkUpdate(description="bulk"),
            initiator=admin_user,
            session=session,
            event_dispatcher=collector,
            selected=[record_id],
        )

    assert [event.succeeded for event in collector.events] == [
        False,
        False,
        False,
        True,
    ]
    assert all("under discovery" in event.details for event in collector.events[:3])
    assert updated_count == 0
    async with db_session_maker() as session:
        stored = await record_queries.get_survey_related_record(session, record_id)
    assert stored is not None
    assert stored.name == record.name
    assert stored.description == record.description
