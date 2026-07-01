import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from ... import errors
from ...schemas import identifiers
from ..queries import recordassets as asset_queries

logger = logging.getLogger(__name__)


async def delete_record_asset(
    session: AsyncSession,
    record_asset_id: identifiers.RecordAssetId,
) -> None:
    if record_asset := (await asset_queries.get_record_asset(session, record_asset_id)):
        await session.delete(record_asset)
        await session.commit()
    else:
        raise errors.SeisLabDataError(
            f"Record asset with id {record_asset!r} does not exist."
        )
