import uuid

import pytest

from seis_lab_data import constants
from seis_lab_data.db.commands import (
    projects as project_commands,
    surveymissions as mission_commands,
)
from seis_lab_data.db.queries import (
    projects as project_queries,
    surveymissions as mission_queries,
    surveyrelatedrecords as record_queries,
)
from seis_lab_data.operations import (
    projects as project_ops,
    surveymissions as mission_ops,
    surveyrelatedrecords as record_ops,
)
from seis_lab_data.schemas import (
    events as event_schemas,
    identifiers,
    surveymissions as mission_schemas,
    surveyrelatedrecords as record_schemas,
)
from seis_lab_data.schemas.identifiers import RequestId


class _EventCollector:
    def __init__(self):
        self.events: list[event_schemas.SeisLabDataEvent] = []

    async def __call__(self, event: event_schemas.SeisLabDataEvent) -> None:
        self.events.append(event)


# publication is automatic, therefore published resources must remain deletable,
# as well as resources whose ancestors are published


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_published_project(
    db_session_maker, published_sample_data, admin_user
):
    project_id = identifiers.ProjectId(published_sample_data["projects"][0].id)
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await project_ops.delete_project(
            request_id=RequestId(uuid.uuid4()),
            project_id=project_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert await project_queries.get_project(session, project_id) is None
    assert dispatcher.events[-1].modification == constants.ResourceModification.DELETED
    assert dispatcher.events[-1].succeeded is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_published_survey_mission_of_published_project(
    db_session_maker, published_sample_data, admin_user
):
    mission_id = identifiers.SurveyMissionId(published_sample_data["missions"][0].id)
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await mission_ops.delete_survey_mission(
            request_id=RequestId(uuid.uuid4()),
            survey_mission_id=mission_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert await mission_queries.get_survey_mission(session, mission_id) is None
    assert dispatcher.events[-1].modification == constants.ResourceModification.DELETED
    assert dispatcher.events[-1].succeeded is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_published_survey_related_record_of_published_mission(
    db_session_maker, published_sample_data, admin_user
):
    record_id = identifiers.SurveyRelatedRecordId(
        published_sample_data["records"][0].id
    )
    dispatcher = _EventCollector()
    async with db_session_maker() as session:
        await record_ops.delete_survey_related_record(
            request_id=RequestId(uuid.uuid4()),
            survey_related_record_id=record_id,
            initiator=admin_user,
            session=session,
            event_dispatcher=dispatcher,
        )
        assert (
            await record_queries.get_survey_related_record(session, record_id) is None
        )
    assert dispatcher.events[-1].modification == constants.ResourceModification.DELETED
    assert dispatcher.events[-1].succeeded is True


# a valid resource is only published if its parent is already published, which
# ensures that published resources never have a parent that is not public


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "project_status, expected_mission_status",
    [
        pytest.param(
            constants.ProjectStatus.DRAFT,
            constants.SurveyMissionStatus.DRAFT,
            id="draft-project",
        ),
        pytest.param(
            constants.ProjectStatus.PUBLISHED,
            constants.SurveyMissionStatus.PUBLISHED,
            id="published-project",
        ),
    ],
)
async def test_valid_survey_mission_is_published_only_if_its_project_is(
    db_session_maker,
    sample_survey_missions,
    admin_user,
    project_status,
    expected_mission_status,
):
    mission_id = identifiers.SurveyMissionId(sample_survey_missions[0].id)
    async with db_session_maker() as session:
        mission = await mission_queries.get_survey_mission(session, mission_id)
        # the project is valid in both cases, only its status differs
        await project_commands.update_project_validation_result(
            session, mission.project, {"is_valid": True, "errors": None}
        )
        await project_commands.set_project_status(
            session, identifiers.ProjectId(mission.project_id), project_status
        )
        await mission_ops.update_survey_mission(
            request_id=RequestId(uuid.uuid4()),
            survey_mission_id=mission_id,
            to_update=mission_schemas.SurveyMissionUpdate(
                description="An updated description for the survey mission",
                bbox_4326="POLYGON ((-10 38, -9 38, -9 39, -10 39, -10 38))",
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
        )
        updated = await mission_queries.get_survey_mission(session, mission_id)
    assert updated.validation_result["is_valid"] is True, updated.validation_result
    assert updated.status == expected_mission_status


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mission_status, expected_record_status",
    [
        pytest.param(
            constants.SurveyMissionStatus.DRAFT,
            constants.SurveyRelatedRecordStatus.DRAFT,
            id="draft-mission",
        ),
        pytest.param(
            constants.SurveyMissionStatus.PUBLISHED,
            constants.SurveyRelatedRecordStatus.PUBLISHED,
            id="published-mission",
        ),
    ],
)
async def test_valid_survey_related_record_is_published_only_if_its_mission_is(
    db_session_maker,
    sample_survey_related_records,
    admin_user,
    mission_status,
    expected_record_status,
):
    record_id = identifiers.SurveyRelatedRecordId(sample_survey_related_records[0].id)
    async with db_session_maker() as session:
        record = await record_queries.get_survey_related_record(session, record_id)
        # the mission is valid in both cases, only its status differs
        await mission_commands.update_survey_mission_validation_result(
            session, record.survey_mission, {"is_valid": True, "errors": None}
        )
        await mission_commands.set_survey_mission_status(
            session,
            identifiers.SurveyMissionId(record.survey_mission_id),
            mission_status,
        )
        await record_ops.update_survey_related_record(
            request_id=RequestId(uuid.uuid4()),
            survey_related_record_id=record_id,
            to_update=record_schemas.SurveyRelatedRecordUpdate(
                description="An updated description for the survey-related record",
                bbox_4326="POLYGON ((-10 38, -9 38, -9 39, -10 39, -10 38))",
            ),
            initiator=admin_user,
            session=session,
            event_dispatcher=_EventCollector(),
        )
        updated = await record_queries.get_survey_related_record(session, record_id)
    assert updated.validation_result["is_valid"] is True, updated.validation_result
    assert updated.status == expected_record_status
