import pytest

from seis_lab_data.db import queries


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_marine_campaigns(sample_marine_campaigns, db_session_maker):
    async with db_session_maker() as session:
        campaigns, total = await queries.list_marine_campaigns(
            session, include_total=True
        )
        assert total == len(sample_marine_campaigns)
