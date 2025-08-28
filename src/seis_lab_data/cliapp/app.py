import json
import uuid
from typing import Annotated

import typer

from .. import (
    operations,
    schemas,
)
from .asynctyper import AsyncTyper

app = AsyncTyper()
marine_campaigns_app = AsyncTyper()
app.add_typer(marine_campaigns_app, name="marine-campaigns")


def parse_json_links(raw_json: str):
    return json.loads(raw_json)


@app.callback()
def app_callback(ctx: typer.Context):
    """SeisLabData main CLI."""


@marine_campaigns_app.callback()
def marine_campaigns_app_callback(ctx: typer.Context):
    """Manage marine campaigns."""


@marine_campaigns_app.async_command(name="create")
async def create_marine_campaign(
    ctx: typer.Context,
    owner: str,
    name_en: str,
    name_pt: str,
    link: Annotated[list[dict], typer.Option(parser=parse_json_links)],
):
    """Create a new marine campaign."""
    session_maker = ctx.obj["session_maker"]
    ctx.obj["main"].status_console.print(f"{link=}")
    async with session_maker() as session:
        created_marine_campaign = await operations.create_marine_campaign(
            to_create=schemas.MarineCampaignCreate(
                id=uuid.uuid4(),
                owner=owner,
                name={"en": name_en, "pt": name_pt},
                links=link,
            ),
            initiator=owner,
            session=session,
            settings=ctx.obj["main"].settings,
        )
        ctx.obj["main"].status_console.print(
            schemas.MarineCampaignReadDetail(**created_marine_campaign.model_dump())
        )


@marine_campaigns_app.async_command(name="list")
async def list_marine_campaigns(
    ctx: typer.Context,
    limit: int = 20,
    offset: int = 0,
):
    """List marine campaigns."""
    settings = ctx.obj["main"].settings
    printer = ctx.obj["main"].status_console.print
    session_maker = ctx.obj["session_maker"]
    async with session_maker() as session:
        items, num_total = await operations.list_marine_campaigns(
            session, settings, limit=limit, offset=offset, include_total=True
        )
    printer(f"Total records: {num_total}")
    for item in items:
        printer(schemas.MarineCampaignReadListItem(**item.model_dump()))
