import uuid

import typer

from .. import (
    operations,
    schemas,
)
from .asynctyper import AsyncTyper

app = AsyncTyper()


@app.callback()
def dev_app_callback(ctx: typer.Context):
    """Dev-related CLI commands."""


@app.async_command()
async def load_sample_marine_campaigns(ctx: typer.Context):
    """Load sample marine campaigns into the database."""
    campaigns_to_create = [
        schemas.MarineCampaignCreate(
            id=uuid.UUID("74f07051-1aa9-4c08-bc27-3ecf101ab5b3"),
            owner="fakeowner1",
            name={"en": "My first campaign", "pt": "A minha primeira campanha"},
            links=[
                {
                    "url": "https://fakeurl.com",
                    "media_type": "text/html",
                    "relation": "related",
                    "description": {
                        "en": "A fake description for link",
                        "pt": "Uma descrição falsa para o link",
                    },
                }
            ],
        ),
        schemas.MarineCampaignCreate(
            id=uuid.UUID("9a877fbe-da98-45ab-af70-711879c6fc01"),
            owner="fakeowner1",
            name={"en": "My second campaign", "pt": "A minha segunda campanha"},
            links=[
                {
                    "url": "https://fakeurl.com",
                    "media_type": "text/html",
                    "relation": "related",
                    "description": {
                        "en": "A fake description for link",
                        "pt": "Uma descrição falsa para o link",
                    },
                }
            ],
        ),
    ]
    session_maker = ctx.obj["session_maker"]
    created = []
    async with session_maker() as session:
        for to_create in campaigns_to_create:
            created.append(
                await operations.create_marine_campaign(
                    to_create,
                    initiator=to_create.owner,
                    session=session,
                    settings=ctx.obj["main"].settings,
                )
            )
    for created_campaign in created:
        to_show = schemas.MarineCampaignReadListItem(**created_campaign.model_dump())
        ctx.obj["main"].status_console.print(to_show)
