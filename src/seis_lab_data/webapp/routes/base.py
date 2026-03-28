import logging

import babel
from starlette_babel import gettext_lazy as _
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ...config import SeisLabDataSettings

logger = logging.getLogger(__name__)


async def home(request: Request):
    template_processor = request.state.templates
    logger.debug(f"{request.user=}")
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
