import logging
import time

import httpx2
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    UnauthenticatedUser,
)
from starlette.requests import HTTPConnection

from ..auth import AuthConfig
from ..config import SeisLabDataSettings
from ..constants import SESSION_USER_CLAIMS
from ..db.commands.users import upsert_user
from ..schemas import identifiers
from ..schemas import user as user_schemas

logger = logging.getLogger(__name__)


class OIDCAuthBackend(AuthenticationBackend):
    def __init__(self, settings: SeisLabDataSettings) -> None:
        self.settings = settings

    async def authenticate(self, conn: HTTPConnection):
        token = conn.session.get("token")
        if not token:
            return AuthCredentials([]), UnauthenticatedUser()

        now = time.time()
        cache_seconds = self.settings.auth_token_introspection_cache_seconds
        introspected_at = conn.session.get("token_introspected_at")
        refreshed = False
        if not (introspected_at and (now - introspected_at) < cache_seconds):
            # the access token must remain valid for as long as the result of this
            # check is cached, otherwise it is renewed right away
            expires_at = token.get("expires_at")
            active = (
                expires_at is None or now + cache_seconds < expires_at
            ) and await self._introspect_token(token["access_token"])
            if not active:
                refresh_result = await self._refresh_token(token.get("refresh_token"))
                if refresh_result is None:
                    conn.session.clear()
                    return AuthCredentials([]), UnauthenticatedUser()
                new_token, user_info = refresh_result
                conn.session["token"] = {
                    "access_token": new_token["access_token"],
                    "token_type": new_token.get("token_type", "Bearer"),
                    "expires_at": now + new_token["expires_in"],
                    # authentik only issues a new refresh token once the current one
                    # is close to expiring, as set by the provider's
                    # refresh_token_threshold
                    "refresh_token": new_token.get(
                        "refresh_token", token["refresh_token"]
                    ),
                }
                conn.session["user"] = {
                    claim: user_info[claim]
                    for claim in SESSION_USER_CLAIMS
                    if claim in user_info
                }
                refreshed = True
            conn.session["token_introspected_at"] = now

        user_info = conn.session.get("user", {})
        id_ = user_info.get("sub")
        if id_ is None:
            return AuthCredentials([]), UnauthenticatedUser()

        user = user_schemas.User(
            id=identifiers.UserId(id_),
            email=user_info.get("email"),
            username=user_info.get("preferred_username"),
            name=user_info.get("name", ""),
            roles=list(user_info.get("roles", [])),
            active=user_info.get("email_verified", False),
        )
        if refreshed:
            try:
                async with self.settings.get_db_session_maker()() as session:
                    await upsert_user(session, user)
            except Exception:
                logger.warning("Failed to upsert user to local DB", exc_info=True)
        return AuthCredentials(["authenticated"]), user

    async def _introspect_token(self, access_token: str) -> bool:
        auth_config = AuthConfig.from_settings(self.settings)
        try:
            async with httpx2.AsyncClient() as client:
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

    async def _refresh_token(
        self, refresh_token: str | None
    ) -> tuple[dict, dict] | None:
        """Obtain a new access token by means of the refresh token grant.

        The user info claims are fetched again with the new access token, which
        keeps the user's roles in sync with authentik for the whole duration of the
        session.

        Returns the token endpoint's response and the user info claims, or `None`
        if the refresh token is missing or authentik rejects it.
        """
        if not refresh_token:
            return None
        auth_config = AuthConfig.from_settings(self.settings)
        try:
            async with httpx2.AsyncClient() as client:
                token_response = await client.post(
                    auth_config.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    auth=(auth_config.client_id, auth_config.client_secret),
                    timeout=5.0,
                )
                token_response.raise_for_status()
                new_token = token_response.json()
                user_info_response = await client.get(
                    auth_config.userinfo_endpoint,
                    headers={"Authorization": f"Bearer {new_token['access_token']}"},
                    timeout=5.0,
                )
                user_info_response.raise_for_status()
            return new_token, user_info_response.json()
        except Exception:
            logger.warning("Token refresh failed — failing closed", exc_info=True)
            return None
