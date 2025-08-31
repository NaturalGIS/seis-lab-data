from starlette_babel import gettext_lazy as _
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
            request.session.get("user"),
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
                schemas.MarineCampaignReadListItem(
                    **i.model_dump(),
                )
                for i in items
            ],
            "num_total": num_total,
            "breadcrumbs": [
                schemas.BreadcrumbItem(
                    name=_("Home"), url=str(request.url_for("home"))
                ),
                schemas.BreadcrumbItem(name=_("Marine campaigns")),
            ],
        },
    )


routes = [
    Route("/", list_marine_campaigns, methods=["GET"], name="list"),
]
