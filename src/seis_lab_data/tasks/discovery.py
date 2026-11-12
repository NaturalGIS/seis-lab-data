import json
import logging
import uuid

import dramatiq

from .. import (
    config,
    constants,
)
from ..operations import discovery as discovery_ops
from ..schemas import (
    discovery as discovery_schemas,
    identifiers,
    user as user_schemas,
)
from . import decorators
from .stub import sld_stub_broker

dramatiq.set_broker(sld_stub_broker)
logger = logging.getLogger(__name__)


@dramatiq.actor
@decorators.sld_settings
async def create_asset_discovery_configuration(
    raw_request_id: str,
    raw_to_create: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await discovery_ops.create_asset_discovery_configuration(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            to_create=discovery_schemas.AssetDiscoveryConfigurationCreate.model_validate_json(
                raw_to_create
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def update_asset_discovery_configuration(
    raw_request_id: str,
    raw_resource_id: str,
    raw_to_update: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await discovery_ops.update_asset_discovery_configuration(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            asset_discovery_configuration_id=identifiers.AssetDiscoveryConfId(
                uuid.UUID(raw_resource_id)
            ),
            to_update=discovery_schemas.AssetDiscoveryConfigurationUpdate.model_validate_json(
                raw_to_update
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor
@decorators.sld_settings
async def delete_asset_discovery_configuration(
    raw_request_id: str,
    raw_resource_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await discovery_ops.delete_asset_discovery_configuration(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            asset_discovery_configuration_id=identifiers.AssetDiscoveryConfId(
                uuid.UUID(raw_resource_id)
            ),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


# We don't want discovery to delay the interactive tasks, so this runs on its
# own queue; also, this gets no retries, we leave a re-run up to the user
@dramatiq.actor(
    queue_name="discovery",
    max_retries=0,
    time_limit=constants.DISCOVERY_TIME_LIMIT_SECONDS * 1000,
)
@decorators.sld_settings
async def discover_survey_mission_contents(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
):
    request_id = identifiers.RequestId(uuid.UUID(raw_request_id))
    mission_id = identifiers.SurveyMissionId(uuid.UUID(raw_survey_mission_id))
    initiator = user_schemas.User(**json.loads(raw_initiator))
    async with settings.get_db_session_maker()() as session:
        await discovery_ops.run_mission_discovery(
            request_id=request_id,
            mission_id=mission_id,
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
            settings=settings,
            user=initiator,
        )


@dramatiq.actor(max_retries=0)
@decorators.sld_settings
async def cancel_survey_mission_discovery(
    raw_request_id: str,
    raw_survey_mission_id: str,
    raw_initiator: str,
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await discovery_ops.cancel_mission_discovery(
            request_id=identifiers.RequestId(uuid.UUID(raw_request_id)),
            mission_id=identifiers.SurveyMissionId(uuid.UUID(raw_survey_mission_id)),
            initiator=user_schemas.User(**json.loads(raw_initiator)),
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )


@dramatiq.actor(max_retries=0, time_limit=60_000)
@decorators.sld_settings
async def recover_stale_survey_mission_discoveries(
    *,
    settings: config.SeisLabDataSettings,
) -> None:
    async with settings.get_db_session_maker()() as session:
        await discovery_ops.recover_stale_mission_discoveries(
            request_id=identifiers.RequestId(uuid.uuid4()),
            initiator_id="system",
            session=session,
            event_dispatcher=settings.get_event_dispatcher(),
        )
