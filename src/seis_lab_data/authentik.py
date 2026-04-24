"""Facilities for dealing with authentik."""

import logging

import httpx

from . import schemas
from .constants import ROLE_ADMIN, ROLE_EDITOR, ROLE_SYSTEM_ADMIN

logger = logging.getLogger(__name__)

_GROUP_ADMIN = "seis-lab-data-catalog-admins"
_GROUP_EDITOR = "seis-lab-data-catalog-editors"


def _roles_from_raw_user(raw_user: dict) -> list[str]:
    roles = []
    if raw_user.get("is_superuser"):
        roles.append(ROLE_SYSTEM_ADMIN)
    group_names = {g["name"] for g in raw_user.get("groups_obj", [])}
    if _GROUP_ADMIN in group_names:
        roles.append(ROLE_ADMIN)
    if _GROUP_EDITOR in group_names:
        roles.append(ROLE_EDITOR)
    return roles


async def get_user_by_username(
    admin_token: str,
    username: str,
    web_client: httpx.AsyncClient,
    authentik_base_url: str,
) -> schemas.User | None:
    """Retrieve user details by username using the authentik API."""
    response = await web_client.get(
        f"{authentik_base_url}/api/v3/core/users/",
        params={"username": username},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    if not response.is_success:
        logger.warning(f"Failed to fetch user {username!r}: {response.status_code}")
        return None
    payload = response.json()
    if payload.get("pagination", {}).get("count", 0) < 1:
        logger.warning(f"User {username!r} not found in Authentik")
        return None
    raw_user = payload["results"][0]
    return schemas.User(
        id=schemas.UserId(raw_user["uuid"]),
        email=raw_user.get("email", ""),
        username=raw_user.get("name", ""),
        roles=_roles_from_raw_user(raw_user),
        active=raw_user.get("is_active", False),
    )


async def get_user_by_uuid(
    admin_token: str,
    user_id: schemas.UserId,
    web_client: httpx.AsyncClient,
    authentik_base_url: str,
) -> schemas.User | None:
    """Retrieve user details using the authentik API"""
    response = await web_client.get(
        f"{authentik_base_url}/api/v3/core/users/",
        params={"uuid": user_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    if not response.is_success:
        logger.warning(f"Failed to fetch user {user_id}: {response.status_code}")
        return None
    payload = response.json()
    if payload.get("pagination", {}).get("count", 0) < 1:
        logger.warning(f"User {user_id} not found")
        return None
    raw_user = payload["results"][0]
    return schemas.User(
        id=user_id,
        email=raw_user.get("email", ""),
        username=raw_user.get("name", ""),
        roles=_roles_from_raw_user(raw_user),
        active=raw_user.get("is_active", False),
    )
