"""Facilities for dealing with authentik."""

import logging

import httpx

from . import schemas

logger = logging.getLogger(__name__)


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
    response.raise_for_status()
    payload = response.json()
    if payload.get("pagination", {}).get("count", 0) < 1:
        logger.warning(f"User {username!r} not found in Authentik")
        return None
    raw_user = payload["results"][0]
    return schemas.User(
        id=schemas.UserId(raw_user["uid"]),
        email=raw_user.get("email", ""),
        username=raw_user.get("username", ""),
        roles=raw_user.get("groups", []),
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
        f"{authentik_base_url}/api/v3/users/",
        params={
            "uuid": user_id,
        },
        headers={
            "Authorization": f"Bearer {admin_token}",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if response.status_code != 200:
        logger.warning(
            f"Failed to fetch user {user_id}: {response.status_code} {response.text}"
        )
        return None
    if payload.get("pagination", {}).get("count") < 1:
        logger.warning(f"User {user_id} not found")
        return None
    raw_user = payload["results"][0]
    return schemas.User(
        id=user_id,
        email=raw_user.get("email", ""),
        username=raw_user.get("username", ""),
        roles=raw_user.get("groups", []),
        active=raw_user.get("is_active", False),
    )
