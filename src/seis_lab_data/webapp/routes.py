import dataclasses
import logging
from starlette_babel import gettext_lazy as _
from starlette.requests import Request
from starlette.routing import Route

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class User:
    email: str
    username: str
    roles: list[str]
    is_authenticated: bool = False

    @classmethod
    def from_request(cls, request: Request) -> "User":
        return cls(
            email=request.headers.get("X-Auth-Request-Email"),
            username=request.headers.get("X-Auth-Request-User"),
            roles=[
                role
                for role in request.headers.get("X-Auth-Request-Roles", "").split(",")
                if role != ""
            ],
            is_authenticated=bool(request.headers.get("X-Auth-Request-Email")),
        )


async def home(request: Request):
    template_processor = request.state.templates
    logger.debug("This is the home route")
    return template_processor.TemplateResponse(
        request, "index.html", context={"greeting": _("Hi there!")}
    )


async def protected(request: Request):
    user = User.from_request(request)
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request, "protected.html", context={"user": user}
    )


routes = [
    Route("/", home),
    Route("/protected", protected),
]
