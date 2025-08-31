import typer
from sqlalchemy.exc import IntegrityError

from .. import (
    events,
    operations,
    schemas,
)
from .asynctyper import AsyncTyper
from .sampledata import MARINE_CAMPAIGNS_TO_CREATE

app = AsyncTyper()


@app.callback()
def dev_app_callback(ctx: typer.Context):
    """Dev-related commands"""


@app.async_command()
async def load_sample_marine_campaigns(ctx: typer.Context):
    """Load sample marine campaigns into the database."""
    session_maker = ctx.obj["session_maker"]
    created = []
    settings = ctx.obj["main"].settings
    async with session_maker() as session:
        for to_create in MARINE_CAMPAIGNS_TO_CREATE:
            try:
                created.append(
                    await operations.create_marine_campaign(
                        to_create,
                        initiator=to_create.owner,
                        session=session,
                        settings=settings,
                        event_emitter=events.get_event_emitter(settings),
                    )
                )
            except IntegrityError:
                ctx.obj["main"].status_console.print(
                    f"Marine campaign {to_create.id!r} already exists, skipping..."
                )
                await session.rollback()
    for created_campaign in created:
        to_show = schemas.MarineCampaignReadListItem(**created_campaign.model_dump())
        ctx.obj["main"].status_console.print(to_show)
