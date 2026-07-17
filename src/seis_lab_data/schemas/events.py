import datetime as dt
import dataclasses
from functools import partial
from typing import TypeAlias

from .. import constants
from . import identifiers


get_utc_now = partial(dt.datetime.now, tz=dt.timezone.utc)


@dataclasses.dataclass(frozen=True, kw_only=True)
class _EventBase:
    initiator: str
    timestamp: dt.datetime = dataclasses.field(default_factory=get_utc_now)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourceModificationEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    parent_resource_id: str | None = (
        None  # mostly useful for when resource is deleted to figure out where to redirect
    )
    modification: constants.ResourceModification
    succeeded: bool
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class BulkResourceModificationEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    modification: constants.BulkResourceModification
    succeeded: bool
    affected_count: int
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourceStatusChangedEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    succeeded: bool
    new_status: str | None
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiscoveryEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.DiscoveryStage
    succeeded: bool
    details: str | None = None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ValidationEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.ValidationStage
    succeeded: bool
    is_valid: bool
    details: str | None = None


SeisLabDataEvent: TypeAlias = (
    ResourceModificationEvent
    | BulkResourceModificationEvent
    | ResourceStatusChangedEvent
    | DiscoveryEvent
    | ValidationEvent
)
