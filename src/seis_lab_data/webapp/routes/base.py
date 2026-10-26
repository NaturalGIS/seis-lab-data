import logging

import babel
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ...config import SeisLabDataSettings
from ...operations import surveymissions as survey_mission_ops
from ...permissions import surveymissions as mission_permissions
from ...schemas import webui as webui_schemas
from .common import get_list_item_permissions

logger = logging.getLogger(__name__)


async def home(request: Request):
    settings: SeisLabDataSettings = request.state.settings
    user = request.user if request.user.is_authenticated else None
    async with settings.get_db_session_maker()() as session:
        # default ordering is by temporal extent, most recent first
        recent_missions, _num_total = await survey_mission_ops.list_survey_missions(
            session, initiator=user, page=1, page_size=3
        )
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request,
        "index.html",
        context={
            "items": [
                webui_schemas.SurveyMissionReadListItem.from_db_instance(i)
                for i in recent_missions
            ],
            "list_item_permissions": get_list_item_permissions(
                user,
                recent_missions,
                mission_permissions.can_update_survey_mission,
                mission_permissions.can_delete_survey_mission,
            ),
        },
    )


async def set_language(request: Request):
    lang = request.path_params["lang"]
    logger.debug(f"{lang=}")
    next_url = request.headers.get("referer", request.url_for("home"))
    response = RedirectResponse(next_url)
    try:
        babel.Locale.parse(lang)
        response.set_cookie("language", lang)
    except babel.UnknownLocaleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return response


async def profile(request: Request):
    settings = request.state.settings
    settings: SeisLabDataSettings
    user = request.user if request.user.is_authenticated else None
    if user:
        return RedirectResponse(
            url=f"{settings.auth_external_base_url}/if/user/", status_code=302
        )
    else:
        return RedirectResponse(url=request.url_for("login"), status_code=302)


async def protected(request: Request):
    if not (user := request.user if request.user.is_authenticated else None):
        return RedirectResponse(url=request.url_for("login"), status_code=302)
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request, "protected.html", context={"user": user}
    )
