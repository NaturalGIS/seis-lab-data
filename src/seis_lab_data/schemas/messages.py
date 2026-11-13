from typing import (
    Annotated,
    Literal,
    TypeAlias,
    TypeVar,
)

from . import identifiers
from .. import constants

import pydantic


IdType = TypeVar("IdType")


class ResourceModificationMessage(pydantic.BaseModel):
    type: Literal["resource_modified"] = "resource_modified"
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    resource_name: str | None = None
    parent_resource_id: str | None = (
        None  # mostly useful for when resource is deleted to figure out where to redirect
    )
    modification: constants.ResourceModification
    succeeded: bool
    details: str | None = None


class BulkResourceModificationMessage(pydantic.BaseModel):
    type: Literal["bulk_resource_modified"] = "bulk_resource_modified"
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    modification: constants.BulkResourceModification
    succeeded: bool
    affected_count: int
    details: str | None = None


class ResourceStatusChangedMessage(pydantic.BaseModel):
    type: Literal["resource_status_changed"] = "resource_status_changed"
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    resource_name: str | None = None
    succeeded: bool
    new_status: str | None
    details: str | None = None


class DiscoveryMessage(pydantic.BaseModel):
    type: Literal["discovery"] = "discovery"
    resource_type: constants.ResourceType
    resource_id: str
    resource_name: str | None = None
    request_id: identifiers.RequestId
    modification: constants.DiscoveryStage
    succeeded: bool
    details: str | None = None


class DerivationMessage(pydantic.BaseModel):
    type: Literal["derivation"] = "derivation"
    resource_type: constants.ResourceType
    resource_id: str
    parent_resource_id: str | None = None
    request_id: identifiers.RequestId


class ValidationMessage(pydantic.BaseModel):
    type: Literal["validation"] = "validation"
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.ValidationStage
    succeeded: bool
    is_valid: bool
    details: str | None = None


class ExportMessage(pydantic.BaseModel):
    type: Literal["export"] = "export"
    resource_type: constants.ResourceType
    resource_id: str
    resource_name: str | None = None
    request_id: identifiers.RequestId
    stage: constants.ExportStage
    succeeded: bool
    details: str | None = None


SldPubSubMessage: TypeAlias = Annotated[
    ResourceModificationMessage
    | BulkResourceModificationMessage
    | DiscoveryMessage
    | DerivationMessage
    | ValidationMessage
    | ResourceStatusChangedMessage
    | ExportMessage,
    pydantic.Field(discriminator="type"),
]
