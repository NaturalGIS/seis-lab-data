import dataclasses
import logging

from authlib.integrations.starlette_client import OAuth

from .config import SeisLabDataSettings
from .constants import AUTH_CLIENT_NAME

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class AuthConfig:
    authentik_internal_url: str
    authentik_external_url: str
    client_id: str
    client_secret: str
    app_slug: str

    @classmethod
    def from_settings(cls, settings: SeisLabDataSettings):
        return cls(
            authentik_external_url=settings.auth_external_base_url,
            authentik_internal_url=settings.auth_internal_base_url,
            client_id=settings.auth_client_id,
            client_secret=settings.auth_client_secret,
            app_slug=settings.auth_application_slug,
        )

    @property
    def authorize_url(self):
        return f"{self.authentik_external_url}/application/o/authorize/"

    @property
    def token_url(self):
        return f"{self.authentik_internal_url}/application/o/token/"

    @property
    def userinfo_endpoint(self):
        return f"{self.authentik_internal_url}/application/o/userinfo/"

    @property
    def end_session_endpoint(self):
        return (
            f"{self.authentik_external_url}/application/o/{self.app_slug}/end-session/"
        )

    @property
    def revocation_endpoint(self):
        return f"{self.authentik_internal_url}/application/o/revoke/"

    @property
    def introspection_endpoint(self):
        return f"{self.authentik_internal_url}/application/o/introspect/"

    @property
    def jwks_uri(self):
        return f"{self.authentik_internal_url}/application/o/{self.app_slug}/jwks/"


def get_oauth_manager(auth_config: AuthConfig):
    oauth = OAuth()
    oauth.register(
        name=AUTH_CLIENT_NAME,
        client_id=auth_config.client_id,
        client_secret=auth_config.client_secret,
        authorize_url=auth_config.authorize_url,
        access_token_url=auth_config.token_url,
        userinfo_endpoint=auth_config.userinfo_endpoint,
        revocation_endpoint=auth_config.revocation_endpoint,
        introspection_endpoint=auth_config.introspection_endpoint,
        jwks_uri=auth_config.jwks_uri,
        client_kwargs={
            "scope": "openid email profile",
        },
        server_metadata={
            "end_session_endpoint": auth_config.end_session_endpoint,
            "revocation_endpoint": auth_config.revocation_endpoint,
            "introspection_endpoint": auth_config.introspection_endpoint,
            "jwks_uri": auth_config.jwks_uri,
        },
    )
    return oauth
