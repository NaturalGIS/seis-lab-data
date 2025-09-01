import logging
import uuid

from starlette_babel import gettext_lazy as _
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
    Mount("/projects", routes=project_routes, name="projects"),
]
