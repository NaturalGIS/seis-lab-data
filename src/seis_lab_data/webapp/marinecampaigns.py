from starlette.requests import Request
from starlette.routing import Route

from .. import (
    operations,
    schemas,
)


async def list_marine_campaigns(request: Request):
    """List marine campaigns."""
    session_maker = request.state.session_maker
    async with session_maker() as session:
        items, num_total = await operations.list_marine_campaigns(
            session,
            request.state.settings,
            initiator=request.session.get("user"),
            limit=request.query_params.get("limit", 20),
            offset=request.query_params.get("offset", 0),
            include_total=True,
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "marinecampaigns/list.html",
        context={
            "items": [
                schemas.MarineCampaignReadListItem(**i.model_dump()) for i in items
            ],
            "num_total": num_total,
        },
    )


routes = [
    Route("/", list_marine_campaigns, methods=["GET"], name="list"),
]
