import pytest

from seis_lab_data.db import queries


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_projects(sample_projects, db_session_maker):
    async with db_session_maker() as session:
        projects, total = await queries.list_projects(session, include_total=True)
        assert total == len(sample_projects)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_missions(sample_survey_missions, db_session_maker):
    async with db_session_maker() as session:
        survey_missions, total = await queries.list_survey_missions(
            session, include_total=True
        )
        assert total == len(sample_survey_missions)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_survey_related_records(
    sample_survey_related_records, db_session_maker
):
    async with db_session_maker() as session:
        survey_records, total = await queries.list_survey_related_records(
            session, include_total=True
        )
        assert total == len(sample_survey_related_records)
