import dataclasses
import logging
import uuid

from starlette_babel import gettext_lazy as _
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Route

from ..config import SeisLabDataSettings
from ..constants import AUTH_CLIENT_NAME
from ..processing import tasks

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
    request_id = str(uuid.uuid4())
    logger.debug("This is the home route")
    tasks.process_data.send(f"hi from the home route with request id {request_id}")
    return template_processor.TemplateResponse(
        request, "index.html", context={"greeting": _("Hi there!")}
    )


async def login(request: Request):
    oauth_manager = request.state.oauth_manager
    oauth_client = oauth_manager.create_client(AUTH_CLIENT_NAME)
    logger.debug(f"{oauth_client=}")
    redirect_uri = request.url_for("auth_callback")
    logger.debug(f"{redirect_uri=}")
    logger.debug(f"{oauth_client.server_metadata=}")
    logger.debug("about to call oauth_client.authorize_redirect...")
    return await oauth_client.authorize_redirect(request, redirect_uri)


async def auth_callback(request: Request):
    try:
        oauth_manager = request.state.oauth_manager
        oauth_client = oauth_manager.create_client(AUTH_CLIENT_NAME)
        logger.debug(f"{oauth_client.server_metadata=}")
        token = await oauth_client.authorize_access_token(request)
        user_info = token.get("userinfo")
        request.session["user"] = user_info
        request.session["token"] = {
            "access_token": token["access_token"],
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
        }
        return RedirectResponse(url=request.url_for("home"), status_code=302)
    except Exception as err:
        logger.error(f"Authentication error: {err}")


async def logout(request: Request):
    request.session.clear()
    logout_url = f"{request.state.auth_config.end_session_endpoint}?next={request.url_for('home')}"
    return RedirectResponse(url=logout_url, status_code=302)


async def profile(request: Request):
    settings = request.state.settings
    settings: SeisLabDataSettings
    user = request.session.get("user")
    if user:
        return RedirectResponse(
            url=f"{settings.auth_external_base_url}/if/user/", status_code=302
        )
    else:
        return RedirectResponse(url=request.url_for("login"), status_code=302)


async def protected(request: Request):
    if not (user := request.session.get("user")):
        return RedirectResponse(url=request.url_for("login"), status_code=302)
    template_processor = request.state.templates
    return template_processor.TemplateResponse(
        request, "protected.html", context={"user": user}
    )


routes = [
    Route("/", home),
    Route("/login", login),
    Route("/oauth2/callback", auth_callback),
    Route("/logout", logout),
    Route("/profile", profile),
    Route("/protected", protected),
]
