from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import (
    Depends,
    Request,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from ... import config


def get_settings(request: Request) -> config.SeisLabDataSettings:
    return request.state.settings


SettingsDep = Annotated[config.SeisLabDataSettings, Depends(get_settings)]


async def get_session(settings: SettingsDep) -> AsyncGenerator[AsyncSession, None]:
    session_maker = settings.get_db_session_maker()
    async with session_maker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
