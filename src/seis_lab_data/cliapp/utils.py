import httpx

from .. import authentik, config, schemas
from ..db import commands as db_commands


async def resolve_admin_user(
    settings: config.SeisLabDataSettings,
    admin_username: str | None = None,
    admin_user_id: str | None = None,
) -> schemas.User:
    async with httpx.AsyncClient() as client:
        if admin_user_id:
            user = await authentik.get_user_by_uuid(
                admin_token=settings.auth_admin_token,
                user_id=schemas.UserId(admin_user_id),
                web_client=client,
                authentik_base_url=settings.auth_internal_base_url,
            )
            identifier = admin_user_id
        elif admin_username:
            user = await authentik.get_user_by_username(
                admin_token=settings.auth_admin_token,
                username=admin_username,
                web_client=client,
                authentik_base_url=settings.auth_internal_base_url,
            )
            identifier = admin_username
        else:
            raise ValueError("Either admin_user_id or admin_username must be provided.")
    if user is None:
        raise ValueError(f"User {identifier!r} not found in Authentik.")
    async with settings.get_db_session_maker()() as session:
        await db_commands.upsert_user(session, user)
    return user
