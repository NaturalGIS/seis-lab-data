import logging
import time

import httpx
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class TokenIntrospectionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"].startswith("/static"):
            await self.app(scope, receive, send)
            return

        session = scope.get("session", {})
        token = session.get("token")
        if not token:
            await self.app(scope, receive, send)
            return

        auth_config = scope["state"]["auth_config"]
        now = time.time()
        introspected_at = session.get("token_introspected_at")
        if (
            introspected_at
            and (now - introspected_at) < auth_config.token_introspection_cache_seconds
        ):
            await self.app(scope, receive, send)
            return

        active = await self._introspect_token(auth_config, token["access_token"])

        if active:
            session["token_introspected_at"] = now
            await self.app(scope, receive, send)
        else:
            session.clear()
            redirect = RedirectResponse(
                url=Request(scope, receive).url_for("login"), status_code=302
            )
            await redirect(scope, receive, send)

    async def _introspect_token(self, auth_config, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    auth_config.introspection_endpoint,
                    data={"token": access_token},
                    auth=(auth_config.client_id, auth_config.client_secret),
                    timeout=5.0,
                )
            return response.json().get("active", False)
        except Exception:
            logger.warning("Token introspection failed — failing closed", exc_info=True)
            return False
