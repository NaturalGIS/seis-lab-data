import logging
from starlette_babel import gettext_lazy as _
from starlette.requests import Request
from starlette.routing import Route

logger = logging.getLogger(__name__)


async def home(request: Request):
    template_processor = request.state.templates
    logger.debug("This is the home route")
    return template_processor.TemplateResponse(
        request, "index.html", context={"greeting": _("Hi there!")}
    )


routes = [
    Route("/", home),
]
