from typing import (
    Annotated,
    Literal,
    TypeVar,
)

import pydantic

from .. import constants
from . import identifiers

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
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = {}


class BulkResourceModificationMessage(pydantic.BaseModel):
    type: Literal["bulk_resource_modified"] = "bulk_resource_modified"
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    modification: constants.BulkResourceModification
    succeeded: bool
    affected_count: int
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = {}


class ResourceStatusChangedMessage(pydantic.BaseModel):
    type: Literal["resource_status_changed"] = "resource_status_changed"
    request_id: identifiers.RequestId
    resource_type: constants.ResourceType
    resource_id: str | None
    resource_name: str | None = None
    succeeded: bool
    new_status: str | None
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = {}


class DiscoveryMessage(pydantic.BaseModel):
    type: Literal["discovery"] = "discovery"
    resource_type: constants.ResourceType
    resource_id: str
    resource_name: str | None = None
    request_id: identifiers.RequestId
    modification: constants.DiscoveryStage
    succeeded: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = {}
    sections_done: int | None = None
    sections_total: int | None = None
    current_section: str | None = None


class DerivationMessage(pydantic.BaseModel):
    type: Literal["derivation"] = "derivation"
    resource_type: constants.ResourceType
    resource_id: str
    parent_resource_id: str | None = None
    request_id: identifiers.RequestId
    stage: constants.DerivationStage
    succeeded: bool


class ValidationMessage(pydantic.BaseModel):
    type: Literal["validation"] = "validation"
    resource_type: constants.ResourceType
    resource_id: str
    request_id: identifiers.RequestId
    modification: constants.ValidationStage
    succeeded: bool
    is_valid: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = {}


class ExportMessage(pydantic.BaseModel):
    type: Literal["export"] = "export"
    resource_type: constants.ResourceType
    resource_id: str
    resource_name: str | None = None
    request_id: identifiers.RequestId
    stage: constants.ExportStage
    succeeded: bool
    # an untranslated message template, translated by the stream handlers
    details: str | None = None
    details_params: dict[str, str | int] = {}


type SldPubSubMessage = Annotated[
    ResourceModificationMessage
    | BulkResourceModificationMessage
    | DiscoveryMessage
    | DerivationMessage
    | ValidationMessage
    | ResourceStatusChangedMessage
    | ExportMessage,
    pydantic.Field(discriminator="type"),
]
