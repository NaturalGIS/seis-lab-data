import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import schemas
from .. import models

logger = logging.getLogger(__name__)


async def upsert_user(session: AsyncSession, user: schemas.User) -> None:
    existing = await session.get(models.User, user.id)
    if existing:
        existing.username = user.username
        existing.email = user.email
        session.add(existing)
    else:
        session.add(models.User(id=user.id, username=user.username, email=user.email))
    await session.commit()
