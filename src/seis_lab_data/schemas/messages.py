from typing import (
    Annotated,
    Literal,
    TypeAlias,
)

from . import identifiers

import pydantic


class ProjectCreationStartedMessage(pydantic.BaseModel):
    type: Literal["project_creation_started"] = "project_creation_started"
    request_id: identifiers.RequestId


class ProjectCreationSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_creation_successful"] = "project_creation_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectCreationFailedMessage(pydantic.BaseModel):
    type: Literal["project_creation_failed"] = "project_creation_failed"
    request_id: identifiers.RequestId
    details: str


class ProjectUpdateStartedMessage(pydantic.BaseModel):
    type: Literal["project_update_started"] = "project_update_started"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectUpdateSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_update_successful"] = "project_update_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectUpdateFailedMessage(pydantic.BaseModel):
    type: Literal["project_update_failed"] = "project_update_failed"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str


class ProjectDeletionStartedMessage(pydantic.BaseModel):
    type: Literal["project_deletion_started"] = "project_deletion_started"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectDeletionSuccessfulMessage(pydantic.BaseModel):
    type: Literal["project_deletion_successful"] = "project_deletion_successful"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId


class ProjectDeletionFailedMessage(pydantic.BaseModel):
    type: Literal["project_deletion_failed"] = "project_deletion_failed"
    request_id: identifiers.RequestId
    project_id: identifiers.ProjectId
    details: str


class HelloMessage(pydantic.BaseModel):
    type: Literal["hello"]
    greeting: str
    sleep_for_seconds: int = 1


SldPubSubMessage: TypeAlias = Annotated[
    ProjectCreationStartedMessage
    | ProjectCreationFailedMessage
    | ProjectCreationSuccessfulMessage
    | ProjectUpdateStartedMessage
    | ProjectUpdateFailedMessage
    | ProjectUpdateSuccessfulMessage
    | ProjectDeletionStartedMessage
    | ProjectDeletionFailedMessage
    | ProjectDeletionSuccessfulMessage
    | HelloMessage,
    pydantic.Field(discriminator="type"),
]
