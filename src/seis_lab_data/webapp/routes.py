import logging
import uuid

import babel
from starlette_babel import (
    gettext_lazy as _,
    get_locale,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import (
    Mount,
    Route,
)

from .auth import get_user
from ..config import SeisLabDataSettings
from ..processing import tasks

from . import auth
from .projects import routes as project_routes

logger = logging.getLogger(__name__)


async def home(request: Request):
    template_processor = request.state.templates
    request_id = str(uuid.uuid4())
    logger.debug("This is the home route")
    logger.debug(f"Request cookies: {request.cookies=}")
    logger.debug(f"Current locale in the request state is {request.state.locale=}")
    logger.debug(
        f"Current locale according to global starlette-babel function {get_locale()=}"
    )
    logger.debug(f"Current language is {request.state.language=}")
    logger.debug("With the global translator that is imported from starlette_babel:")
    logger.debug(_("Hi there!"))
    tasks.process_data.send(f"hi from the home route with request id {request_id}")
    return template_processor.TemplateResponse(
        request, "index.html", context={"greeting": _("Hi there!")}
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
