import dataclasses
import datetime as dt
from functools import partial

from .. import constants
from . import identifiers

get_utc_now = partial(dt.datetime.now, tz=dt.UTC)


@dataclasses.dataclass(frozen=True, kw_only=True)
class _EventBase:
    initiator: str
    timestamp: dt.datetime = dataclasses.field(default_factory=get_utc_now)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourceModificationEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    # shown in notifications; None if the resource could not be found
    resource_name: str | None
    parent_resource_id: str | None = (
        None  # mostly useful for when resource is deleted to figure out where to redirect
    )
    modification: constants.ResourceModification
    succeeded: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True)
class BulkResourceModificationEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    modification: constants.BulkResourceModification
    succeeded: bool
    affected_count: int
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourceStatusChangedEvent(_EventBase):
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    # shown in notifications; None if the resource could not be found
    resource_name: str | None
    succeeded: bool
    new_status: str | None
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True)
class DiscoveryEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    # shown in notifications; None if the resource could not be found
    resource_name: str | None
    request_id: identifiers.RequestId
    modification: constants.DiscoveryStage
    succeeded: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True)
class DerivationEvent(_EventBase):
    """Derived assets, such as previews, were stored for a resource."""

    resource_type: constants.ResourceType
    resource_id: str
    parent_resource_id: str | None = None
    request_id: identifiers.RequestId


@dataclasses.dataclass(frozen=True, kw_only=True)
class ValidationEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.ValidationStage
    succeeded: bool
    is_valid: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, kw_only=True)
class ExportEvent(_EventBase):
    resource_type: constants.ResourceType
    resource_id: str
    # shown in notifications; None if the resource could not be found
    resource_name: str | None
    request_id: identifiers.RequestId
    stage: constants.ExportStage
    succeeded: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = dataclasses.field(default_factory=dict)


type SeisLabDataEvent = (
    ResourceModificationEvent
    | BulkResourceModificationEvent
    | ResourceStatusChangedEvent
    | DiscoveryEvent
    | DerivationEvent
    | ValidationEvent
    | ExportEvent
)
