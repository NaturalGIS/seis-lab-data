import logging
import uuid

import babel
from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import (
    Mount,
    Route,
)

from ..auth import get_user
from ..config import SeisLabDataSettings
from ..processing import tasks

from . import auth
from .projects import routes as project_routes

logger = logging.getLogger(__name__)


async def home(request: Request):
    template_processor = request.state.templates
    request_id = str(uuid.uuid4())
    logger.debug("This is the home route")
    tasks.process_data.send(f"hi from the home route with request id {request_id}")
    return template_processor.TemplateResponse(
        request, "index.html", context={"greeting": _("Hi there!")}
    )


async def set_language(request: Request):
    lang = request.path_params["lang"]
    next_ = request.query_params.get("next", request.url_for("home"))
    logger.debug(f"{lang=}")
    logger.debug(f"{next_=}")
    try:
        locale = babel.Locale.parse(lang)
    except babel.UnknownLocaleError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if (user := get_user(request.session.get("user", {}))) is not None:
        logger.debug(f"{user=}")
        user.preferred_language = locale.language
        logger.debug(f"{user.preferred_language=}")
    else:
        request.state.locale = locale
    return RedirectResponse(next_)


async def profile(request: Request):
    settings = request.state.settings
    settings: SeisLabDataSettings
    user = get_user(request.session.get("user", {}))
    if user:
        return RedirectResponse(
            url=f"{settings.auth_external_base_url}/if/user/", status_code=302
        )
    else:
        return RedirectResponse(url=request.url_for("login"), status_code=302)


async def protected(request: Request):
    if not (user := get_user(request.session.get("user", {}))):
        return RedirectResponse(url=request.url_for("login"), status_code=302)
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request, "protected.html", context={"user": user}
    )


routes = [
    Route("/", home),
    Route("/login", auth.login),
    Route("/oauth2/callback", auth.auth_callback),
    Route("/logout", auth.logout),
    Route("/profile", profile),
    Route("/protected", protected),
    Route("/set-language/{lang}", set_language, name="set_language"),
    Mount("/projects", routes=project_routes, name="projects"),
]
