import inspect
import logging
from collections.abc import Callable
from functools import wraps

import httpx2
from datastar_py import ServerSentEventGenerator
from datastar_py.starlette import DatastarResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ...constants import (
    AUTH_CLIENT_NAME,
    SESSION_USER_CLAIMS,
)
from ...db.commands.users import upsert_user
from ...schemas import identifiers
from ...schemas import user as user_schemas

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
        request.session["user"] = {
            claim: user_info[claim]
            for claim in SESSION_USER_CLAIMS
            if claim in user_info
        }
        request.session["token"] = {
            # NOTE: do not store the id_token on the session
            # browser cookies are typically not allowed to be bigger than 4096 chars
            # and when they do, the cookie can be silently dropped, causing
            # our logins to not work
            "access_token": token["access_token"],
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
            "refresh_token": token.get("refresh_token"),
        }
        user = get_user(user_info)
        if user:
            session_maker = request.state.settings.get_db_session_maker()
            try:
                async with session_maker() as session:
                    await upsert_user(session, user)
            except Exception:
                logger.warning("Failed to upsert user to local DB", exc_info=True)
        return RedirectResponse(url=request.url_for("home"), status_code=302)
    except Exception:
        logger.exception("Authentication error")
        return RedirectResponse(url=request.url_for("login"), status_code=302)


async def logout(request: Request):
    # Ending the authentik session at the end_session endpoint does not invalidate
    # the refresh token, nor the access tokens obtained with it after the authentik
    # session had already ended, therefore both are revoked explicitly
    token = request.session.get("token") or {}
    auth_config = request.state.auth_config
    async with httpx2.AsyncClient() as client:
        for token_type_hint in ("refresh_token", "access_token"):
            if not (token_value := token.get(token_type_hint)):
                continue
            try:
                response = await client.post(
                    auth_config.revocation_endpoint,
                    data={"token": token_value, "token_type_hint": token_type_hint},
                    auth=(auth_config.client_id, auth_config.client_secret),
                    timeout=5.0,
                )
                response.raise_for_status()
            except Exception:
                logger.warning(f"Failed to revoke the {token_type_hint}", exc_info=True)
    request.session.clear()
    response = RedirectResponse(url=auth_config.end_session_endpoint, status_code=302)
    response.delete_cookie("id_token")
    return response


def get_user(
    user_info: dict,
) -> user_schemas.User | None:
    id_ = user_info.get("sub")
    if id_ is None:
        return None
    return user_schemas.User(
        id=identifiers.UserId(id_),
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

        for value in bound_args.arguments.values():
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

                return DatastarResponse(event_streamer(), status_code=200)
            else:
                return RedirectResponse(url=request.url_for("login"), status_code=302)

        return await route_function(*args, **kwargs)

    return wrapper
