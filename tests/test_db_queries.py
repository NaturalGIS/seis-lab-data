import uuid

import pytest

from seis_lab_data.db import queries


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_projects(sample_projects, db_session_maker):
    async with db_session_maker() as session:
        projects, total = await queries.list_projects(session, include_total=True)
        assert total == len(sample_projects)


@pytest.mark.parametrize(
    "project_id_filter, expected_total",
    [
        pytest.param(None, 5),
        pytest.param(uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3"), 3),
    ],
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_missions(
    sample_survey_missions, db_session_maker, project_id_filter, expected_total
):
    async with db_session_maker() as session:
        survey_missions, total = await queries.list_survey_missions(
            session, project_id=project_id_filter, include_total=True
        )
        assert total == expected_total


@pytest.mark.parametrize(
    "survey_mission_id_filter, expected_total",
    [
        pytest.param(None, 2),
        pytest.param(uuid.UUID("cfe10cd8-5a5e-40e4-807b-7064f94a2edf"), 1),
    ],
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_related_records(
    sample_survey_related_records,
    db_session_maker,
    survey_mission_id_filter,
    expected_total,
):
    async with db_session_maker() as session:
        survey_records, total = await queries.list_survey_related_records(
            session, survey_mission_id=survey_mission_id_filter, include_total=True
        )
        assert total == expected_total
