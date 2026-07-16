import json
import logging
import uuid

import dramatiq

from .. import config
from ..operations import datasetcategories as category_ops
from ..schemas import (
    datasetcategories as category_schemas,
    identifiers,
    user as user_schemas,
)

from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)

logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def create_dataset_category(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await category_ops.create_dataset_category(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_create=category_schemas.DatasetCategoryCreate.model_validate_json(
                raw_to_create
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def update_dataset_category(
    raw_request_id: str,
    raw_resource_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    logger.debug(f"{locals()=}")
    async with settings.get_db_session_maker()() as session:
        await category_ops.update_dataset_category(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            resource_id=identifiers.DatasetCategoryId(uuid.UUID(raw_resource_id)),
            to_update=category_schemas.DatasetCategoryUpdate.model_validate_json(
                raw_to_update
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def delete_dataset_category(
    raw_request_id: str,
    raw_resource_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await category_ops.delete_dataset_category(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            resource_id=identifiers.DatasetCategoryId(uuid.UUID(raw_resource_id)),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
