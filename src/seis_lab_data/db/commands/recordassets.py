from sqlmodel.ext.asyncio.session import AsyncSession

from ... import (
    errors,
    schemas,
)
from .. import queries


async def delete_record_asset(
    session: AsyncSession,
    record_asset_id: schemas.RecordAssetId,
) -> None:
    if record_asset := (await queries.get_record_asset(session, record_asset_id)):
        await session.delete(record_asset)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Record asset with id {record_asset!r} does not exist."
        )
