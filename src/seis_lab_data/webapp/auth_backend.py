import logging
import time

import httpx
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    UnauthenticatedUser,
)
from starlette.requests import HTTPConnection

from ..auth import AuthConfig
from ..config import SeisLabDataSettings
from .. import schemas

logger = logging.getLogger(__name__)


class OIDCAuthBackend(AuthenticationBackend):
    def __init__(self, settings: SeisLabDataSettings) -> None:
        self.settings = settings

    async def authenticate(self, conn: HTTPConnection):
        token = conn.session.get("token")
        logger.debug(f"{token=}")
        if not token:
            return AuthCredentials([]), UnauthenticatedUser()

        now = time.time()
        introspected_at = conn.session.get("token_introspected_at")
        if not (
            introspected_at
            and (now - introspected_at)
            < self.settings.auth_token_introspection_cache_seconds
        ):
            active = await self._introspect_token(token["access_token"])
            if not active:
                conn.session.clear()
                return AuthCredentials([]), UnauthenticatedUser()
            conn.session["token_introspected_at"] = now

        user_info = conn.session.get("user", {})
        id_ = user_info.get("sub")
        if id_ is None:
            return AuthCredentials([]), UnauthenticatedUser()

        return AuthCredentials(["authenticated"]), schemas.User(
            id=schemas.UserId(id_),
            email=user_info.get("email"),
            username=user_info.get("preferred_username"),
            roles=list(user_info.get("roles", [])),
            active=user_info.get("email_verified", False),
        )

    async def _introspect_token(self, access_token: str) -> bool:
        auth_config = AuthConfig.from_settings(self.settings)
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
