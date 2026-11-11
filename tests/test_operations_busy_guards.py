"""Resources whose status shows a task is working on them must not be modified."""

import uuid

import pytest

from seis_lab_data import (
    constants,
    errors,
)
from seis_lab_data.db.commands import (
    projects as project_commands,
    surveymissions as mission_commands,
    surveyrelatedrecords as record_commands,
)
from seis_lab_data.db.queries import (
    projects as project_queries,
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
)
from seis_lab_data.operations import (
    discovery as discovery_ops,
    projects as project_ops,
    surveymissions as mission_ops,
)
from seis_lab_data.schemas import (
    events as event_schemas,
    identifiers,
    projects as project_schemas,
    surveymissions as mission_schemas,
)
from seis_lab_data.schemas.identifiers import RequestId


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_refuses_survey_mission_under_discovery(
    db_session_maker, sample_survey_missions, admin_user
):
    mission_id = identifiers.SurveyMissionId(sample_survey_missions[0].id)
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, mission_id, constants.SurveyMissionStatus.UNDER_DISCOVERY
        )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        with pytest.raises(errors.SeisLabDataError):
            await mission_ops.update_survey_mission(
                request_id=RequestId(uuid.uuid4()),
                survey_mission_id=mission_id,
                to_update=mission_schemas.SurveyMissionUpdate(
                    description="Should not apply"
                ),
                initiator=admin_user,
                session=session,
                event_dispatcher=dispatcher,
            )
        mission = await mission_queries.get_survey_mission(session, mission_id)
    assert mission.description != "Should not apply"
    assert mission.status == constants.SurveyMissionStatus.UNDER_DISCOVERY
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_refuses_survey_mission_under_discovery(
    db_session_maker, sample_survey_missions, admin_user
):
    mission_id = identifiers.SurveyMissionId(sample_survey_missions[0].id)
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, mission_id, constants.SurveyMissionStatus.UNDER_DISCOVERY
        )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await mission_ops.delete_survey_mission(
            request_id=RequestId(uuid.uuid4()),
            survey_mission_id=mission_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert await mission_queries.get_survey_mission(session, mission_id)
    assert dispatcher.events[-1].modification == constants.ResourceModification.DELETED
    assert dispatcher.events[-1].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_refuses_survey_mission_with_a_busy_record(
    db_session_maker, sample_survey_related_records, admin_user
):
    record = sample_survey_related_records[0]
    record_id = identifiers.SurveyRelatedRecordId(record.id)
    mission_id = identifiers.SurveyMissionId(record.survey_mission_id)
    async with db_session_maker() as session:
        await record_commands.set_survey_related_record_status(
            session, record_id, constants.SurveyRelatedRecordStatus.UNDER_DERIVATION
        )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await mission_ops.delete_survey_mission(
            request_id=RequestId(uuid.uuid4()),
            survey_mission_id=mission_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert await mission_queries.get_survey_mission(session, mission_id)
        assert await record_queries.get_survey_related_record(session, record_id)
    assert dispatcher.events[-1].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_refuses_project_under_validation(
    db_session_maker, sample_projects, admin_user
):
    project_id = identifiers.ProjectId(sample_projects[0].id)
    async with db_session_maker() as session:
        await project_commands.set_project_status(
            session, project_id, constants.ProjectStatus.UNDER_VALIDATION
        )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        with pytest.raises(errors.SeisLabDataError):
            await project_ops.update_project(
                request_id=RequestId(uuid.uuid4()),
                project_id=project_id,
                to_update=project_schemas.ProjectUpdate(description="Should not apply"),
                initiator=admin_user,
                session=session,
                event_dispatcher=dispatcher,
            )
        project = await project_queries.get_project(session, project_id)
    assert project.description != "Should not apply"
    assert dispatcher.events[-1].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "busy_level",
    [
        pytest.param("project", id="busy-project"),
        pytest.param("mission", id="busy-mission"),
        pytest.param("record", id="busy-record"),
    ],
)
async def test_delete_refuses_project_with_busy_contents(
    db_session_maker, sample_survey_related_records, admin_user, busy_level
):
    record = sample_survey_related_records[0]
    record_id = identifiers.SurveyRelatedRecordId(record.id)
    mission_id = identifiers.SurveyMissionId(record.survey_mission_id)
    async with db_session_maker() as session:
        mission = await mission_queries.get_survey_mission(session, mission_id)
        project_id = identifiers.ProjectId(mission.project_id)
        if busy_level == "project":
            await project_commands.set_project_status(
                session, project_id, constants.ProjectStatus.UNDER_VALIDATION
            )
        elif busy_level == "mission":
            await mission_commands.set_survey_mission_status(
                session, mission_id, constants.SurveyMissionStatus.UNDER_DISCOVERY
            )
        else:
            await record_commands.set_survey_related_record_status(
                session, record_id, constants.SurveyRelatedRecordStatus.UNDER_EXPORT
            )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await project_ops.delete_project(
            request_id=RequestId(uuid.uuid4()),
            project_id=project_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert await project_queries.get_project(session, project_id)
        assert await record_queries.get_survey_related_record(session, record_id)
    assert dispatcher.events[-1].modification == constants.ResourceModification.DELETED
    assert dispatcher.events[-1].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_mission_publication_leaves_busy_missions_alone(
    db_session_maker, sample_survey_missions
):
    mission_id = identifiers.SurveyMissionId(sample_survey_missions[0].id)
    async with db_session_maker() as session:
        mission = await mission_queries.get_survey_mission(session, mission_id)
        await mission_commands.update_survey_mission_validation_result(
            session, mission, {"is_valid": True, "errors": None}
        )
        await mission_commands.set_survey_mission_status(
            session, mission_id, constants.SurveyMissionStatus.UNDER_DISCOVERY
        )
        published_ids = (
            await mission_commands.bulk_publish_valid_survey_missions_for_project(
                session, identifiers.ProjectId(mission.project_id)
            )
        )
        mission = await mission_queries.get_survey_mission(session, mission_id)
    assert mission_id not in published_ids
    assert mission.status == constants.SurveyMissionStatus.UNDER_DISCOVERY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovery_refuses_survey_mission_already_under_discovery(
    db_session_maker, settings, sample_survey_missions, admin_user
):
    mission_id = identifiers.SurveyMissionId(sample_survey_missions[0].id)
    async with db_session_maker() as session:
        await mission_commands.set_survey_mission_status(
            session, mission_id, constants.SurveyMissionStatus.UNDER_DISCOVERY
        )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await discovery_ops.run_mission_discovery(
            request_id=RequestId(uuid.uuid4()),
            mission_id=mission_id,
            session=session,
            event_dispatcher=dispatcher,
            settings=settings,
            user=admin_user,
        )
        mission = await mission_queries.get_survey_mission(session, mission_id)
    # the refused run must not reset the status of the discovery still going on
    assert mission.status == constants.SurveyMissionStatus.UNDER_DISCOVERY
    assert len(dispatcher.events) == 1
    assert dispatcher.events[0].modification == constants.DiscoveryStage.ENDED
    assert dispatcher.events[0].succeeded is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_only_one_of_concurrent_mission_status_flips_wins(
    db_session_maker, sample_survey_missions
):
    mission_id = identifiers.SurveyMissionId(sample_survey_missions[0].id)
    async with db_session_maker() as session:
        mission = await mission_queries.get_survey_mission(session, mission_id)
        original_status = mission.status
        first = await mission_commands.compare_and_set_survey_mission_status(
            session,
            mission_id,
            original_status,
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
        )
        second = await mission_commands.compare_and_set_survey_mission_status(
            session,
            mission_id,
            original_status,
            constants.SurveyMissionStatus.UNDER_DISCOVERY,
        )
        mission = await mission_queries.get_survey_mission(session, mission_id)
    assert first is True
    assert second is False
    assert mission.status == constants.SurveyMissionStatus.UNDER_DISCOVERY
