import logging

from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..constants import AUTH_CLIENT_NAME

logger = logging.getLogger(__name__)


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
        request.session["user"] = {
            "preferred_language": request.state.settings.locales[0],
            **user_info,
        }
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
