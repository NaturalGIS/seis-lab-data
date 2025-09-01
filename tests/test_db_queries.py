import pytest

from seis_lab_data.db import queries


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_projects(sample_projects, db_session_maker):
    async with db_session_maker() as session:
        projects, total = await queries.list_projects(session, include_total=True)
        assert total == len(sample_projects)
