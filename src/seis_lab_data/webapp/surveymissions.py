from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.routing import Route

from .. import (
    errors,
    operations,
    schemas,
)
from .auth import get_user


async def list_survey_missions(request: Request):
    """List survey missions."""
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        items, num_total = await operations.list_survey_missions(
            session,
            initiator=user.id if user else None,
            limit=request.query_params.get("limit", 20),
            offset=request.query_params.get("offset", 0),
            include_total=True,
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-missions/list.html",
        context={
            "items": [
                schemas.SurveyMissionReadListItem(
                    **i.model_dump(),
                )
                for i in items
            ],
            "num_total": num_total,
            "breadcrumbs": [
                schemas.BreadcrumbItem(name=_("Home"), url=request.url_for("home")),
                schemas.BreadcrumbItem(name=_("Survey Missions")),
            ],
        },
    )


async def get_survey_mission(request: Request):
    """Get survey mission."""
    slug = request.path_params["survey_mission_slug"]
    session_maker = request.state.session_maker
    user = get_user(request.session.get("user", {}))
    async with session_maker() as session:
        try:
            survey_mission = await operations.get_survey_mission_by_slug(
                slug,
                user.id if user else None,
                session,
                request.state.settings,
            )
        except errors.SeisLabDataError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    if survey_mission is None:
        raise HTTPException(
            status_code=404, detail=_(f"Survey mission {slug!r} not found.")
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "survey-missions/detail.html",
        context={
            "item": schemas.SurveyMissionReadDetail(**survey_mission.model_dump()),
            "breadcrumbs": [
                schemas.BreadcrumbItem(
                    name=_("Home"), url=str(request.url_for("home"))
                ),
                schemas.BreadcrumbItem(
                    name=_("Survey Missions"),
                    url=request.url_for("survey_missions:list"),
                ),
                schemas.BreadcrumbItem(
                    name=survey_mission.name["en"],
                ),
            ],
        },
    )


routes = [
    Route("/", list_survey_missions, methods=["GET"], name="list"),
    Route("/{survey_mission_slug}", get_survey_mission, methods=["GET"], name="detail"),
]
