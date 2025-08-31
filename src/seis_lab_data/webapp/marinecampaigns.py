from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
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
                schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                schemas.BreadcrumbItem(name=_("Marine campaigns")),
            ],
        },
    )


async def get_marine_campaign(request: Request):
    """Get marine campaign."""
    slug = request.path_params["marine_campaign_slug"]
    session_maker = request.state.session_maker
    async with session_maker() as session:
        campaign = await operations.get_marine_campaign_by_slug(
            slug,
            request.session.get("user"),
            session,
            request.state.settings,
        )
    if campaign is None:
        raise HTTPException(
            status_code=404, detail=_(f"Marine campaign {slug!r} not found.")
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "marinecampaigns/detail.html",
        context={
            "item": schemas.MarineCampaignReadDetail(**campaign.model_dump()),
            "breadcrumbs": [
                schemas.BreadcrumbItem(
                    name=_("Home"), url=str(request.url_for("home"))
                ),
                schemas.BreadcrumbItem(
                    name=_("Marine campaigns"),
                    url=request.url_for("marine-campaigns:list"),
                ),
                schemas.BreadcrumbItem(
                    name=campaign.name["en"],
                ),
            ],
        },
    )


routes = [
    Route("/", list_marine_campaigns, methods=["GET"], name="list"),
    Route(
        "/{marine_campaign_slug}", get_marine_campaign, methods=["GET"], name="detail"
    ),
]
