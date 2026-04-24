import inspect
import logging
from functools import wraps
from typing import Callable

from datastar_py import ServerSentEventGenerator
from datastar_py.starlette import DatastarResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse

from seis_lab_data import schemas
from seis_lab_data.constants import AUTH_CLIENT_NAME
from seis_lab_data.db import commands

logger = logging.getLogger(__name__)


async def login(request: Request):
    logger.debug(f"Session ID at login start: {request.session.get('_id')}")
    logger.debug(f"Session contents: {dict(request.session)=}")
    oauth_manager = request.state.oauth_manager
    oauth_client = oauth_manager.create_client(AUTH_CLIENT_NAME)
    logger.debug(f"{oauth_client=}")
    redirect_uri = request.url_for("auth_callback")
    logger.debug(f"{redirect_uri=}")
    logger.debug(f"{oauth_client.server_metadata=}")
    logger.debug("about to call oauth_client.authorize_redirect...")
    response = await oauth_client.authorize_redirect(request, redirect_uri)
    logger.debug(f"Session contents after authorize_redirect: {dict(request.session)=}")
    return response


async def auth_callback(request: Request):
    try:
        oauth_manager = request.state.oauth_manager
        oauth_client = oauth_manager.create_client(AUTH_CLIENT_NAME)
        token = await oauth_client.authorize_access_token(request)
        user_info = token.get("userinfo")
        request.session["user"] = user_info
        request.session["token"] = {
            # NOTE: do not store the id_token on the session
            # browser cookies are typically not allowed to be bigger than 4096 chars
            # and when they do, the cookie can be silently dropped, causing
            # our logins to not work
            "access_token": token["access_token"],
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
        }
        user = get_user(user_info)
        if user:
            session_maker = request.state.settings.get_db_session_maker()
            try:
                async with session_maker() as session:
                    await commands.upsert_user(session, user)
            except Exception:
                logger.warning("Failed to upsert user to local DB", exc_info=True)
        response = RedirectResponse(url=request.url_for("home"), status_code=302)
        id_token = token.get("id_token")
        if id_token:
            # The id_token is stored in a separate cookie (not the session) so it
            # can be passed as id_token_hint to authentik's end_session endpoint at
            # logout time. It cannot go in the session cookie because the combined
            # size would exceed the browser's ~4096 byte cookie limit, causing the
            # session cookie to be silently dropped and login to break.
            response.set_cookie("id_token", id_token, httponly=True, samesite="lax")
        return response
    except Exception as err:
        logger.error(f"Authentication error: {err}")
        return RedirectResponse(url=request.url_for("login"), status_code=302)


async def logout(request: Request):
    id_token = request.cookies.get("id_token")
    request.session.clear()
    params = f"post_logout_redirect_uri={request.url_for('home')}&client_id={request.state.auth_config.client_id}"
    if id_token:
        params += f"&id_token_hint={id_token}"
    logout_url = f"{request.state.auth_config.end_session_endpoint}?{params}"
    response = RedirectResponse(url=logout_url, status_code=302)
    response.delete_cookie("id_token")
    return response


def get_user(
    user_info: dict,
) -> schemas.User | None:
    id_ = user_info.get("sub")
    if id_ is None:
        return None
    return schemas.User(
        id=schemas.UserId(id_),
        email=user_info.get("email"),
        username=user_info.get("preferred_username"),
        roles=[role for role in user_info.get("roles", [])],
        active=user_info.get("email_verified"),
    )


def requires_auth(route_function: Callable):
    sig = inspect.signature(route_function)

    @wraps(route_function)
    async def wrapper(*args, **kwargs):
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        for name, value in bound_args.arguments.items():
            if isinstance(value, Request):
                request = value
                break
        else:
            raise ValueError("No Request parameter found in route function.")

        if not request.user.is_authenticated:
            if request.headers.get("Datastar-Request") == "true":

                async def event_streamer():
                    yield ServerSentEventGenerator.redirect(
                        str(request.url_for("login"))
                    )

                return DatastarResponse(event_streamer(), status_code=302)
            else:
                return RedirectResponse(url=request.url_for("login"), status_code=302)

        return await route_function(*args, **kwargs)

    return wrapper
