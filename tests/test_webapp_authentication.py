"""User sessions

Users log in with the authentik identity provider. A logged in user remains logged in
for as long as they keep using the application, up to a week after their last visit,
and the user's roles are kept in sync with authentik for the whole duration of the
session. Logging out ends the session and invalidates its credentials.
"""

# authentik is faked: its token, introspection, userinfo and revocation endpoints are
# served by an `httpx2.MockTransport`.

import base64
import dataclasses
import functools
import json
import time

import httpx2
import pytest
from authlib.integrations.starlette_client import StarletteOAuth2App
from starlette.testclient import TestClient

from seis_lab_data import constants
from seis_lab_data.db import models

pytestmark = pytest.mark.integration


@dataclasses.dataclass
class _FakeAuthentik:
    claims: dict
    rotate_refresh_tokens: bool = True
    active_access_tokens: set[str] = dataclasses.field(
        default_factory=lambda: {"access-1"}
    )
    valid_refresh_tokens: set[str] = dataclasses.field(
        default_factory=lambda: {"refresh-1"}
    )
    used_refresh_tokens: list[str] = dataclasses.field(default_factory=list)
    introspected_access_tokens: list[str] = dataclasses.field(default_factory=list)
    revoked: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    issued: int = 1

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        form = dict(httpx2.QueryParams(request.content.decode()))
        match request.url.path:
            case "/application/o/introspect/":
                self.introspected_access_tokens.append(form["token"])
                return httpx2.Response(
                    200, json={"active": form["token"] in self.active_access_tokens}
                )
            case "/application/o/token/":
                refresh_token = form["refresh_token"]
                self.used_refresh_tokens.append(refresh_token)
                if refresh_token not in self.valid_refresh_tokens:
                    return httpx2.Response(400, json={"error": "invalid_grant"})
                self.issued += 1
                access_token = f"access-{self.issued}"
                self.active_access_tokens.add(access_token)
                # an expiry of zero makes the next request renew the token again
                response = {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 0,
                }
                if self.rotate_refresh_tokens:
                    self.valid_refresh_tokens.remove(refresh_token)
                    response["refresh_token"] = f"refresh-{self.issued}"
                    self.valid_refresh_tokens.add(response["refresh_token"])
                return httpx2.Response(200, json=response)
            case "/application/o/userinfo/":
                access_token = request.headers["Authorization"].removeprefix("Bearer ")
                if access_token not in self.active_access_tokens:
                    return httpx2.Response(401)
                return httpx2.Response(200, json=self.claims)
            case "/application/o/revoke/":
                self.revoked.append((form["token_type_hint"], form["token"]))
                return httpx2.Response(200)
        return httpx2.Response(404)


@pytest.fixture
def fake_authentik(settings, monkeypatch):
    """Serve the authentik endpoints with a fake and check the token on each request."""
    fake = _FakeAuthentik(
        claims={
            "sub": "some-user",
            "email": "someone@tests.dev",
            "email_verified": True,
            "preferred_username": "someone",
            "name": "Some One",
            "roles": [],
            # claims which the application does not use
            "groups": ["some-group"],
            "sid": "some-authentik-session",
            "nonce": "some-nonce",
        }
    )
    monkeypatch.setattr(
        httpx2,
        "AsyncClient",
        functools.partial(
            httpx2.AsyncClient, transport=httpx2.MockTransport(fake.handle)
        ),
    )
    monkeypatch.setattr(settings, "auth_token_introspection_cache_seconds", 0)
    return fake


def _log_in(
    test_client: TestClient, monkeypatch, claims: dict, expires_at: float
) -> httpx2.Response:
    async def authorize_access_token(self, request, **kwargs):
        return {
            "access_token": "access-1",
            "token_type": "Bearer",
            "expires_at": expires_at,
            "refresh_token": "refresh-1",
            "id_token": "some-id-token",
            "userinfo": dict(claims),
        }

    monkeypatch.setattr(
        StarletteOAuth2App, "authorize_access_token", authorize_access_token
    )
    return test_client.get("/oauth2/callback", follow_redirects=False)


def _is_logged_in(test_client: TestClient) -> bool:
    response = test_client.get("/", params={"lang": "en"})
    assert response.status_code == 200
    return 'aria-label="logout-nav"' in response.text


def test_session_outlives_browser_restart(test_client: TestClient, db, monkeypatch):
    """The session is kept by the browser for a week, rather than only until the
    browser is closed.
    """
    response = _log_in(
        test_client,
        monkeypatch,
        {"sub": "some-user", "email": "someone@tests.dev"},
        time.time() + 3600,
    )
    cookies = {
        header.split("=", 1)[0]: header.lower()
        for header in response.headers.get_list("set-cookie")
    }
    assert "max-age=604800" in cookies["session"]


def _get_session_user_claims(test_client: TestClient) -> set[str]:
    payload = test_client.cookies["session"].split(".")[0]
    payload += "=" * (-len(payload) % 4)
    return set(json.loads(base64.b64decode(payload))["user"])


def test_session_keeps_only_required_user_details(
    test_client: TestClient, db, monkeypatch, fake_authentik
):
    """Of the user details provided by authentik, only those required by the
    application are kept in the session, both at login and when the credentials are
    renewed, so that the session does not exceed the size browsers accept.
    """
    expected = {"sub", "email", "email_verified", "preferred_username", "name", "roles"}
    _log_in(test_client, monkeypatch, fake_authentik.claims, time.time() - 1)
    assert _get_session_user_claims(test_client) == expected
    assert _is_logged_in(test_client)
    assert fake_authentik.used_refresh_tokens == ["refresh-1"]
    assert _get_session_user_claims(test_client) == expected


def test_valid_access_token_is_not_renewed(
    test_client: TestClient, db, monkeypatch, fake_authentik
):
    """A user whose credentials are still valid stays logged in without them being
    renewed.
    """
    _log_in(test_client, monkeypatch, fake_authentik.claims, time.time() + 3600)
    assert _is_logged_in(test_client)
    assert fake_authentik.introspected_access_tokens == ["access-1"]
    assert fake_authentik.used_refresh_tokens == []


@pytest.mark.parametrize("rotate_refresh_tokens", [True, False])
def test_expired_access_token_is_renewed(
    test_client: TestClient, db, monkeypatch, fake_authentik, rotate_refresh_tokens
):
    """A user whose credentials have expired stays logged in, as the credentials are
    renewed with authentik, whether or not authentik replaces the long-lived
    credential used for renewing them.
    """
    fake_authentik.rotate_refresh_tokens = rotate_refresh_tokens
    _log_in(test_client, monkeypatch, fake_authentik.claims, time.time() - 1)
    assert _is_logged_in(test_client)
    assert _is_logged_in(test_client)
    assert fake_authentik.used_refresh_tokens == (
        ["refresh-1", "refresh-2"] if rotate_refresh_tokens else ["refresh-1"] * 2
    )


def test_rejected_renewal_logs_user_out(
    test_client: TestClient, db, monkeypatch, fake_authentik
):
    """A user is logged out when their credentials have expired and authentik refuses
    to renew them, as happens when the user has been deactivated or has not used the
    application for over a week.
    """
    fake_authentik.valid_refresh_tokens.clear()
    _log_in(test_client, monkeypatch, fake_authentik.claims, time.time() - 1)
    assert not _is_logged_in(test_client)
    assert not _is_logged_in(test_client)
    assert fake_authentik.used_refresh_tokens == ["refresh-1"]


def test_renewal_updates_user_roles_and_details(
    test_client: TestClient, db, sync_db_engine, monkeypatch, fake_authentik
):
    """Changes made in authentik to a logged in user's roles and details take effect
    when their credentials are next renewed, without the user having to log in again.
    """
    _log_in(test_client, monkeypatch, fake_authentik.claims, time.time() + 3600)
    response = test_client.get("/projects/", params={"lang": "en"})
    assert 'aria-label="new-project"' not in response.text

    fake_authentik.claims["roles"] = [constants.ROLE_EDITOR]
    fake_authentik.claims["email"] = "someone-else@tests.dev"
    fake_authentik.active_access_tokens.clear()
    response = test_client.get("/projects/", params={"lang": "en"})
    assert 'aria-label="new-project"' in response.text
    with sync_db_engine.connect() as connection:
        db_user = connection.execute(
            models.User.__table__.select().where(models.User.id == "some-user")
        ).one()
    assert db_user.email == "someone-else@tests.dev"


def test_logout_revokes_credentials(
    test_client: TestClient, db, monkeypatch, fake_authentik
):
    """Logging out ends the session and revokes its credentials in authentik, so that
    they can no longer be used, and ends the user's session in authentik.
    """
    _log_in(test_client, monkeypatch, fake_authentik.claims, time.time() + 3600)
    response = test_client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].endswith("/end-session/")
    assert fake_authentik.revoked == [
        ("refresh_token", "refresh-1"),
        ("access_token", "access-1"),
    ]
    assert not _is_logged_in(test_client)
