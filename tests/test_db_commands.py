import uuid

import pytest

from seis_lab_data.db import commands
from seis_lab_data import schemas


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_marine_campaign(db, db_session_maker):
    to_create = schemas.MarineCampaignCreate(
        id=uuid.UUID("5fe24752-5919-4a05-be46-aed53a6936db"),
        owner="fakeowner",
        name={"en": "A fake campaign", "pt": "Uma campanha falsa"},
        root_path="/fake-path/to/fake-campaign/",
    )
    async with db_session_maker() as session:
        created = await commands.create_marine_campaign(session, to_create)
        assert created.id == to_create.id
        assert created.owner == to_create.owner
        assert created.slug == "a-fake-campaign"
        assert created.name["en"] == to_create.name["en"]
        assert created.name["pt"] == to_create.name["pt"]
